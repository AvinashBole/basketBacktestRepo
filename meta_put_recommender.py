from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from rank_put_trades import rank_puts_for_symbol


def run_meta_scan(
    symbols: list[str],
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
    overall_top_n: int,
    avoid_earnings: bool = False,
    max_per_sector: int = 20,
) -> pd.DataFrame:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_rows = []
    failures = []

    for symbol in symbols:
        symbol_output_dir = output_path / symbol.replace("/", "_")
        print(f"\n=== Scanning {symbol} ===")
        try:
            recommendations = rank_puts_for_symbol(
                symbol=symbol,
                data_dir=data_dir,
                output_dir=str(symbol_output_dir),
                start_date=start_date,
                min_open_interest=min_open_interest,
                min_volume=min_volume,
                max_dte=max_dte,
                top_n=top_n,
                min_credit=min_credit,
                max_otm_pct=max_otm_pct,
                max_spread_pct=max_spread_pct,
                avoid_earnings=avoid_earnings,
            )
            recommendations = recommendations.copy()
            recommendations["symbol_output_dir"] = str(symbol_output_dir)
            all_rows.append(recommendations)
        except Exception as exc:
            print(f"Skipping {symbol}: {exc}")
            failures.append({"symbol": symbol, "error": str(exc)})

    if not all_rows:
        raise ValueError("No successful symbol scans completed.")

    combined = pd.concat(all_rows, ignore_index=True)
    
    # Primary Sort
    combined = combined.sort_values(
        ["historical_survival_pct", "final_score", "yield_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    # Sector Diversification
    diversified_rows = []
    sector_counts = {}
    for _, row in combined.iterrows():
        sec = row.get("sector", "Unknown")
        count = sector_counts.get(sec, 0)
        if count < max_per_sector:
            diversified_rows.append(row)
            sector_counts[sec] = count + 1
        if len(diversified_rows) >= overall_top_n:
            break
    
    top_overall = pd.DataFrame(diversified_rows)

    combined_file = output_path / "meta_put_recommendations_all.csv"
    top_file = output_path / "meta_put_recommendations_top.csv"
    combined.to_csv(combined_file, index=False)
    top_overall.to_csv(top_file, index=False)
    print(f"\nSaved combined recommendations: {combined_file}")
    print(f"Saved top overall recommendations: {top_file}")

    if failures:
        failure_df = pd.DataFrame(failures)
        failure_file = output_path / "meta_put_recommendation_failures.csv"
        failure_df.to_csv(failure_file, index=False)
        print(f"Saved failures: {failure_file}")

    return top_overall


def load_symbols_from_args(symbols: list[str] | None, symbols_file: str | None) -> list[str]:
    if symbols:
        return symbols
    if not symbols_file:
        raise ValueError("Provide either --symbols or --symbols-file.")

    path = Path(symbols_file)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        if "symbol" in df.columns:
            column = "symbol"
        else:
            column = df.columns[0]
        return [str(x).strip().upper() for x in df[column].dropna().tolist() if str(x).strip()]

    return [line.strip().upper() for line in path.read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Run the put recommender across multiple symbols and produce a combined leaderboard."
    )
    parser.add_argument("--symbols", nargs="+", default=None, help="Symbols to scan, e.g. --symbols QQQ META TSLA NVDA")
    parser.add_argument("--symbols-file", default=None, help="CSV/txt file of symbols; useful with generate_option_symbol_candidates.py")
    parser.add_argument("--data-dir", default=".", help="Folder for historical price CSV files")
    parser.add_argument("--output-dir", default="meta_outputs", help="Folder for meta-scan outputs")
    parser.add_argument("--start-date", default="2018-01-01", help="Start date for historical price pull")
    parser.add_argument("--min-open-interest", type=int, default=100, help="Minimum option open interest")
    parser.add_argument("--min-volume", type=int, default=1, help="Minimum option volume")
    parser.add_argument("--max-dte", type=int, default=90, help="Maximum days to expiration to analyze")
    parser.add_argument("--top-n", type=int, default=1, help="Recommendations to keep per horizon bucket per symbol")
    parser.add_argument("--min-credit", type=float, default=0.10, help="Minimum premium credit per share")
    parser.add_argument("--max-otm-pct", type=float, default=30.0, help="Maximum strike distance OTM percent")
    parser.add_argument("--max-spread-pct", type=float, default=80.0, help="Maximum bid/ask spread as percent of credit")
    parser.add_argument("--overall-top-n", type=int, default=20, help="Top combined rows to keep in the summary file")
    parser.add_argument("--avoid-earnings", action="store_true", help="Filter out trades that expire after an earnings date")
    parser.add_argument("--max-per-sector", type=int, default=3, help="Max entries per sector in the leaderboard")
    args = parser.parse_args()

    symbols = load_symbols_from_args(args.symbols, args.symbols_file)

    top_overall = run_meta_scan(
        symbols=symbols,
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
        overall_top_n=args.overall_top_n,
        avoid_earnings=args.avoid_earnings,
        max_per_sector=args.max_per_sector,
    )

    display_cols = [
        "symbol",
        "sector",
        "expiration",
        "dte",
        "has_earnings",
        "earnings_date",
        "strike",
        "otm_pct",
        "yield_pct",
        "historical_survival_pct",
        "iv",
        "hv",
        "vrp_ratio",
        "final_score",
    ]
    print("\nTop overall recommendations:")
    print(top_overall[display_cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
