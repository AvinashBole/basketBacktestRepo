from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from us_data_downloader import download_us_symbol, sanitize_symbol
from us_options_data_puller import fetch_option_chain, fetch_option_expirations


HORIZONS = [1, 2, 3, 4, 5, 6, 7, 15, 30, 45, 60, 90]


def find_price_history_file(symbol: str, search_dir: str) -> str | None:
    safe_symbol = sanitize_symbol(symbol)
    candidates = sorted(Path(search_dir).glob(f"{safe_symbol}_*_to_*.csv"))
    return str(candidates[-1]) if candidates else None


def load_or_download_price_history(symbol: str, data_dir: str, start_date: str) -> str:
    existing = find_price_history_file(symbol, data_dir)
    if existing:
        print(f"Using existing price history: {existing}")
        return existing

    end_date = date.today().strftime("%Y-%m-%d")
    return download_us_symbol(symbol, start_date, end_date, output_dir=data_dir)


def load_price_history(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    df = df[pd.to_datetime(df["Date"], errors="coerce").notna()].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Close", "Low"]).sort_values("Date").reset_index(drop=True)
    return df


def build_forward_drop_cache(df: pd.DataFrame) -> dict[int, np.ndarray]:
    close = df["Close"].to_numpy()
    low = df["Low"].to_numpy()
    cache = {}
    for horizon in HORIZONS:
        drops = []
        end = len(df) - horizon
        for i in range(end):
            future_low = np.min(low[i + 1 : i + horizon + 1])
            drop_pct = (close[i] - future_low) / close[i] * 100.0
            drops.append(drop_pct)
        cache[horizon] = np.array(drops)
    return cache


def build_summary(symbol: str, cache: dict[int, np.ndarray], output_dir: str) -> pd.DataFrame:
    rows = []
    for horizon, arr in cache.items():
        rows.append(
            {
                "symbol": symbol,
                "horizon_days": horizon,
                "samples": len(arr),
                "p90_drop_pct": np.percentile(arr, 90),
                "p95_drop_pct": np.percentile(arr, 95),
                "p99_drop_pct": np.percentile(arr, 99),
                "max_drop_pct": np.max(arr),
            }
        )
    summary = pd.DataFrame(rows)
    summary_file = Path(output_dir) / f"{sanitize_symbol(symbol)}_forward_drop_summary.csv"
    summary.to_csv(summary_file, index=False)
    print(f"Saved historical summary: {summary_file}")
    return summary


def nearest_horizon(dte: int) -> int:
    return min(HORIZONS, key=lambda x: abs(x - dte))


def fetch_live_spot(symbol: str, fallback_spot: float) -> float:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        for field in ("lastPrice", "regularMarketPrice", "previousClose"):
            value = info.get(field)
            if value is not None and float(value) > 0:
                return float(value)
    except Exception:
        pass
    return float(fallback_spot)


def select_credit(row: pd.Series) -> float:
    bid = pd.to_numeric(row.get("bid"), errors="coerce")
    ask = pd.to_numeric(row.get("ask"), errors="coerce")
    last = pd.to_numeric(row.get("lastPrice"), errors="coerce")
    if pd.notna(bid) and bid > 0:
        return float(bid)
    if pd.notna(bid) and pd.notna(ask) and bid >= 0 and ask > 0:
        return float((bid + ask) / 2.0)
    if pd.notna(last) and last > 0:
        return float(last)
    return 0.0


def rank_puts_for_symbol(
    symbol: str,
    data_dir: str,
    output_dir: str,
    start_date: str,
    min_open_interest: int,
    min_volume: int,
    max_dte: int,
    top_n: int,
    min_credit: float,
    max_otm_pct: float,
    max_spread_pct: float,
) -> pd.DataFrame:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    current_date = date.today()
    price_file = load_or_download_price_history(symbol, data_dir, start_date)
    prices = load_price_history(price_file)
    drop_cache = build_forward_drop_cache(prices)
    build_summary(symbol, drop_cache, output_dir)

    historical_spot = float(prices.iloc[-1]["Close"])
    spot = fetch_live_spot(symbol, historical_spot)

    _, expirations = fetch_option_expirations(symbol)
    if not expirations:
        raise ValueError(f"No option expirations found for {symbol}.")

    rows = []
    for expiration in expirations:
        expiry_date = datetime.strptime(expiration, "%Y-%m-%d").date()
        dte = (expiry_date - current_date).days
        if dte <= 0 or dte > max_dte:
            continue

        horizon = nearest_horizon(dte)
        chain = fetch_option_chain(symbol, expiration)
        puts = chain.puts.copy()
        if puts.empty:
            continue

        puts["strike"] = pd.to_numeric(puts["strike"], errors="coerce")
        puts["bid"] = pd.to_numeric(puts["bid"], errors="coerce")
        puts["ask"] = pd.to_numeric(puts["ask"], errors="coerce")
        puts["lastPrice"] = pd.to_numeric(puts["lastPrice"], errors="coerce")
        puts["openInterest"] = pd.to_numeric(puts["openInterest"], errors="coerce").fillna(0)
        puts["volume"] = pd.to_numeric(puts["volume"], errors="coerce").fillna(0)
        puts = puts.dropna(subset=["strike"])
        puts = puts[puts["strike"] < spot]
        puts = puts[(puts["openInterest"] >= min_open_interest) & (puts["volume"] >= min_volume)]

        if puts.empty:
            continue

        historical = drop_cache[horizon]
        for _, put in puts.iterrows():
            credit = select_credit(put)
            if credit <= 0:
                continue

            strike = float(put["strike"])
            otm_pct = (spot - strike) / spot * 100.0
            if otm_pct > max_otm_pct:
                continue
            survival = float((historical < otm_pct).mean() * 100.0)
            breach = 100.0 - survival
            yield_pct = credit / strike * 100.0
            annualized_yield_pct = yield_pct * (365.0 / max(dte, 1))
            spread_pct = (
                ((put["ask"] - put["bid"]) / credit) * 100.0
                if pd.notna(put["ask"]) and pd.notna(put["bid"]) and credit > 0
                else np.nan
            )
            if credit < min_credit:
                continue
            if pd.notna(spread_pct) and spread_pct > max_spread_pct:
                continue

            rows.append(
                {
                    "symbol": symbol,
                    "scan_date": current_date.isoformat(),
                    "spot": round(spot, 2),
                    "historical_spot": round(historical_spot, 2),
                    "expiration": expiration,
                    "dte": dte,
                    "mapped_horizon": horizon,
                    "strike": strike,
                    "otm_pct": otm_pct,
                    "credit": credit,
                    "yield_pct": yield_pct,
                    "annualized_yield_pct": annualized_yield_pct,
                    "historical_survival_pct": survival,
                    "historical_breach_pct": breach,
                    "open_interest": int(put["openInterest"]),
                    "volume": int(put["volume"]),
                    "bid": put["bid"],
                    "ask": put["ask"],
                    "spread_pct_of_credit": spread_pct,
                    "score": annualized_yield_pct * (survival / 100.0),
                }
            )

    ranked = pd.DataFrame(rows)
    if ranked.empty:
        raise ValueError("No qualifying put candidates found after filters.")

    ranked = ranked.sort_values(
        ["historical_survival_pct", "score", "yield_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    best_by_dte = ranked.groupby("mapped_horizon", as_index=False).head(top_n)
    ranked_file = Path(output_dir) / f"{sanitize_symbol(symbol)}_put_trade_rankings.csv"
    best_file = Path(output_dir) / f"{sanitize_symbol(symbol)}_put_trade_recommendations.csv"
    ranked.to_csv(ranked_file, index=False)
    best_by_dte.to_csv(best_file, index=False)
    print(f"Saved full rankings: {ranked_file}")
    print(f"Saved recommendations: {best_file}")
    return best_by_dte


def main():
    parser = argparse.ArgumentParser(
        description="Rank put-selling candidates using Yahoo option chains and historical forward-drop analysis."
    )
    parser.add_argument("symbol", help="Ticker symbol, e.g. QQQ, TSLA, META")
    parser.add_argument("--data-dir", default=".", help="Folder for historical price CSV files")
    parser.add_argument("--output-dir", default="outputs", help="Folder for ranking outputs")
    parser.add_argument("--start-date", default="2018-01-01", help="Start date for historical price pull")
    parser.add_argument("--min-open-interest", type=int, default=100, help="Minimum option open interest")
    parser.add_argument("--min-volume", type=int, default=1, help="Minimum option volume")
    parser.add_argument("--max-dte", type=int, default=90, help="Maximum days to expiration to analyze")
    parser.add_argument("--top-n", type=int, default=1, help="Recommendations to keep per horizon bucket")
    parser.add_argument("--min-credit", type=float, default=0.10, help="Minimum premium credit per share")
    parser.add_argument("--max-otm-pct", type=float, default=30.0, help="Maximum strike distance OTM percent")
    parser.add_argument("--max-spread-pct", type=float, default=80.0, help="Maximum bid/ask spread as percent of credit")
    args = parser.parse_args()

    recommendations = rank_puts_for_symbol(
        symbol=args.symbol,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        start_date=args.start_date,
        min_open_interest=args.min_open_interest,
        min_volume=args.min_volume,
        max_dte=args.max_dte,
        top_n=args.top_n,
        min_credit=args.min_credit,
        max_otm_pct=args.max_otm_pct,
        max_spread_pct=args.max_spread_pct,
    )

    display_cols = [
        "symbol",
        "expiration",
        "dte",
        "mapped_horizon",
        "strike",
        "otm_pct",
        "credit",
        "yield_pct",
        "annualized_yield_pct",
        "historical_survival_pct",
        "historical_breach_pct",
        "open_interest",
        "volume",
        "score",
    ]
    print("\nTop recommendations:")
    print(recommendations[display_cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
