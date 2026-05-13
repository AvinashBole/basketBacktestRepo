from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf


DEFAULT_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "AAPL",
    "MSFT",
    "NVDA",
    "META",
    "AMZN",
    "GOOGL",
    "TSLA",
    "AMD",
    "NFLX",
    "SMCI",
    "PLTR",
    "COIN",
    "MSTR",
    "AVGO",
    "ARM",
    "MU",
]


def load_symbols(universe_file: str | None) -> list[str]:
    if not universe_file:
        return DEFAULT_UNIVERSE

    path = Path(universe_file)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        first_col = df.columns[0]
        return [str(x).strip().upper() for x in df[first_col].dropna().tolist() if str(x).strip()]

    symbols = []
    for line in path.read_text().splitlines():
        value = line.strip().upper()
        if value:
            symbols.append(value)
    return symbols


def fetch_symbol_snapshot(symbol: str) -> dict | None:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1d", auto_adjust=False)
        if hist.empty or len(hist) < 2:
            return None

        latest = hist.iloc[-1]
        prev = hist.iloc[-2]
        close = float(latest["Close"])
        prev_close = float(prev["Close"])
        daily_move_pct = ((close - prev_close) / prev_close) * 100.0 if prev_close else 0.0
        dollar_volume = close * float(latest["Volume"])

        options = ticker.options
        option_exp_count = len(options)
        if option_exp_count == 0:
            return None

        return {
            "symbol": symbol,
            "close": close,
            "prev_close": prev_close,
            "daily_move_pct": daily_move_pct,
            "abs_daily_move_pct": abs(daily_move_pct),
            "volume": float(latest["Volume"]),
            "dollar_volume": dollar_volume,
            "option_expirations": option_exp_count,
            "first_expiration": options[0] if options else None,
        }
    except Exception:
        return None


def build_candidates(symbols: list[str], top_n: int) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        snapshot = fetch_symbol_snapshot(symbol)
        if snapshot:
            rows.append(snapshot)

    if not rows:
        raise ValueError("No symbols produced usable option-enabled snapshots.")

    df = pd.DataFrame(rows)
    df["liquidity_rank"] = df["dollar_volume"].rank(ascending=False, method="min")
    df["move_rank"] = df["abs_daily_move_pct"].rank(ascending=False, method="min")
    df["composite_score"] = (
        df["abs_daily_move_pct"] * 0.6
        + (df["dollar_volume"] / df["dollar_volume"].max()) * 100.0 * 0.4
    )
    df = df.sort_values(
        ["composite_score", "abs_daily_move_pct", "dollar_volume"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    return df.head(top_n)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a symbol candidate file for the meta put recommender using live movers/liquidity."
    )
    parser.add_argument("--universe-file", default=None, help="Optional txt/csv file of symbols to scan")
    parser.add_argument("--output-file", default="option_symbol_candidates.csv", help="Where to save the candidate list")
    parser.add_argument("--top-n", type=int, default=10, help="How many symbols to keep")
    args = parser.parse_args()

    symbols = load_symbols(args.universe_file)
    candidates = build_candidates(symbols, args.top_n)
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output_path, index=False)
    print(f"Saved candidates: {output_path}")
    print(candidates.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
