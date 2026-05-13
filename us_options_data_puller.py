import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf


def sanitize_symbol(symbol):
    return re.sub(r"[^A-Za-z0-9_-]", "", symbol.replace("=", ""))


def fetch_option_expirations(symbol):
    ticker = yf.Ticker(symbol)
    expirations = ticker.options
    return ticker, expirations


def download_option_chain(symbol, expiration, output_dir="."):
    print(f"Downloading option chain for {symbol} expiry {expiration}...")

    ticker = yf.Ticker(symbol)
    chain = ticker.option_chain(expiration)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    safe_symbol = sanitize_symbol(symbol)
    calls_file = output_path / f"{safe_symbol}_{expiration}_calls.csv"
    puts_file = output_path / f"{safe_symbol}_{expiration}_puts.csv"

    calls = chain.calls.copy()
    puts = chain.puts.copy()

    if calls.empty and puts.empty:
        print(f"No options data found for {symbol} on {expiration}.")
        return None

    if not calls.empty:
        calls.insert(0, "symbol", symbol)
        calls.insert(1, "expiration", expiration)
        calls.to_csv(calls_file, index=False)
        print(f"Saved calls: {calls_file}")
    else:
        print("No calls returned.")

    if not puts.empty:
        puts.insert(0, "symbol", symbol)
        puts.insert(1, "expiration", expiration)
        puts.to_csv(puts_file, index=False)
        print(f"Saved puts: {puts_file}")
    else:
        print("No puts returned.")

    return {
        "calls_file": str(calls_file) if not calls.empty else None,
        "puts_file": str(puts_file) if not puts.empty else None,
        "calls_rows": len(calls),
        "puts_rows": len(puts),
    }


def download_all_option_chains(symbol, output_dir="."):
    print(f"Fetching expirations for {symbol}...")
    ticker, expirations = fetch_option_expirations(symbol)

    if not expirations:
        print(f"No option expirations found for {symbol}.")
        return []

    print(f"Found {len(expirations)} expirations.")
    for exp in expirations[:10]:
        print(f"  {exp}")
    if len(expirations) > 10:
        print("  ...")

    results = []
    for expiration in expirations:
        result = download_option_chain(symbol, expiration, output_dir=output_dir)
        if result:
            results.append(result)

    summary = pd.DataFrame(results)
    safe_symbol = sanitize_symbol(symbol)
    summary_file = Path(output_dir) / f"{safe_symbol}_option_chain_summary.csv"
    summary.to_csv(summary_file, index=False)
    print(f"Saved summary: {summary_file}")

    return results


if __name__ == "__main__":
    symbol = input("Enter symbol (e.g. QQQ, TSLA, SPY, ^NDX): ").strip()
    mode = input("Download single expiry or all expiries? (single/all) [default=single]: ").strip().lower() or "single"
    output_dir = input("Enter output folder [default=.]: ").strip() or "."

    try:
        ticker, expirations = fetch_option_expirations(symbol)

        if not expirations:
            print(f"No option expirations found for {symbol}.")
        else:
            print(f"Available expirations for {symbol}:")
            for exp in expirations:
                print(f"  {exp}")

            if mode == "all":
                download_all_option_chains(symbol, output_dir=output_dir)
            else:
                expiration = input("Enter one expiration from the list above (YYYY-MM-DD): ").strip()
                if expiration not in expirations:
                    print("Invalid expiration selected.")
                else:
                    download_option_chain(symbol, expiration, output_dir=output_dir)
    except Exception as e:
        print(f"Error: {e}")
