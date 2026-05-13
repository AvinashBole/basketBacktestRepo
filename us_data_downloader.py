import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path
import re


def sanitize_symbol(symbol):
    return re.sub(r"[^A-Za-z0-9_-]", "", symbol.replace("=", ""))


def download_us_symbol(symbol, start_date, end_date, interval="1d", output_dir="."):
    print(f"Downloading {symbol} from {start_date} to {end_date} ({interval})...")

    if interval != "1d":
        print("Warning: Intraday data is limited (~60 days) on free Yahoo Finance.")

    data = yf.download(symbol, start=start_date, end=end_date, interval=interval)

    if data.empty:
        print(f"No data found for {symbol}.")
        return None

    data.reset_index(inplace=True)
    data = data[["Date", "Open", "High", "Low", "Close", "Volume"]]
    data.insert(0, "symbol", symbol)
    data["Date"] = data["Date"].dt.strftime("%Y-%m-%d")

    start_str = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    end_str = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = output_path / f"{sanitize_symbol(symbol)}_{start_str}_to_{end_str}.csv"

    data.to_csv(filename, index=False)
    print(f"Saved: {filename}")
    return str(filename)


if __name__ == "__main__":
    symbols = ["NQ=F", "QQQ", "TSLA", "NVDA", "META"]
    start_date = "2018-01-01"
    end_date = "2026-05-13"

    for symbol in symbols:
        download_us_symbol(symbol, start_date, end_date, interval="1d")
