"""
OPEN-TO-CLOSE BASKET BACKTEST
Buy at open price, sell at close price (same day trading)
"""

import pandas as pd
import numpy as np
import warnings
import sys
import argparse

warnings.filterwarnings('ignore')

def run_open_to_close_backtest(
    signals_file,
    prices_file,
    max_basket_size=20,
    price_date_start=None,
    price_date_end=None
):
    print("=" * 80)
    print("OPEN-TO-CLOSE BASKET BACKTEST")
    print("=" * 80)
    print(f"Max Basket Size: {max_basket_size} stocks")

    # Load data
    print("\n[1/4] Loading data...")
    signals_df = pd.read_csv(signals_file)
    prices_df = pd.read_csv(prices_file)
    
    # Check required columns
    if 'open' not in prices_df.columns:
        raise ValueError("Prices file must contain 'open' column for open-to-close trading")
    
    req_px = ['symbol', 'date', 'open', 'close']
    if not all(c in prices_df.columns for c in req_px):
        raise ValueError(f"Prices file must contain columns: {req_px}")

    # Process dates
    print("\n[2/4] Processing dates...")
    signals_df['datetime'] = pd.to_datetime(signals_df['date'], errors='coerce')
    signals_df['trade_ts'] = signals_df['datetime'].dt.normalize()
    prices_df['date'] = pd.to_datetime(prices_df['date'], errors='coerce')
    prices_df['date_norm'] = prices_df['date'].dt.normalize()

    # Filter price data by date range
    if price_date_start:
        start_ts = pd.to_datetime(price_date_start).normalize()
        prices_df = prices_df[prices_df['date_norm'] >= start_ts]
    if price_date_end:
        end_ts = pd.to_datetime(price_date_end).normalize()
        prices_df = prices_df[prices_df['date_norm'] <= end_ts]

    # Filter signals to price range
    price_min_ts = prices_df['date_norm'].min()
    price_max_ts = prices_df['date_norm'].max()
    signals_df = signals_df[(signals_df['trade_ts'] >= price_min_ts) & (signals_df['trade_ts'] <= price_max_ts)]

    print(f"  ✓ Signals: {len(signals_df)} rows, {signals_df['trade_ts'].nunique()} dates")

    # Create baskets
    print("\n[3/4] Creating baskets...")
    groups = signals_df.groupby('trade_ts')['symbol'].apply(list).reset_index()
    groups.columns = ['trade_ts', 'stocks']
    groups['stocks'] = groups['stocks'].apply(lambda lst: lst[:max_basket_size])
    groups['num_stocks'] = groups['stocks'].apply(len)

    print(f"  ✓ Created {len(groups)} baskets")

    # Run backtest
    print("\n[4/4] Running open-to-close backtest...")
    all_trades = []

    for i, row in groups.iterrows():
        trade_ts = row['trade_ts']
        basket_stocks = row['stocks']

        # Get same-day open and close prices
        day_prices = prices_df[(prices_df['date_norm'] == trade_ts) &
                              (prices_df['symbol'].isin(basket_stocks))][['symbol', 'open', 'close']]

        if len(day_prices) < max(1, int(len(basket_stocks) * 0.5)):
            continue

        # Calculate basket performance
        basket_open_sum = day_prices['open'].sum()
        basket_close_sum = day_prices['close'].sum()
        return_pct = (basket_close_sum - basket_open_sum) / basket_open_sum * 100.0

        all_trades.append({
            'basket_id': i + 1,
            'trade_date': trade_ts.date(),
            'num_stocks': len(day_prices),
            'basket_open_sum': float(basket_open_sum),
            'basket_close_sum': float(basket_close_sum),
            'return_pct': float(return_pct),
            'stocks': ", ".join(day_prices['symbol'].tolist())
        })

    trades_df = pd.DataFrame(all_trades)
    
    if len(trades_df) == 0:
        raise ValueError("No trades executed!")

    # Calculate summary
    total_trades = len(trades_df)
    win_rate = (trades_df['return_pct'] > 0).mean() * 100.0

    summary_df = pd.DataFrame([{
        'Total_Baskets': total_trades,
        'Win_Rate_Percent': float(win_rate),
        'Average_Return_Percent': float(trades_df['return_pct'].mean()),
        'Best_Return_Percent': float(trades_df['return_pct'].max()),
        'Worst_Return_Percent': float(trades_df['return_pct'].min()),
        'Positive_Days': int((trades_df['return_pct'] > 0).sum()),
        'Negative_Days': int((trades_df['return_pct'] < 0).sum())
    }])

    # Save results
    trades_df.to_csv('open_to_close_trades.csv', index=False)
    summary_df.to_csv('open_to_close_summary.csv', index=False)

    print(f"\n✅ Completed {total_trades} open-to-close trades")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Avg Return: {trades_df['return_pct'].mean():.4f}%")

    return {'trades': trades_df, 'summary': summary_df}

def main():
    parser = argparse.ArgumentParser(description='Open-to-Close Basket Backtest')
    parser.add_argument('signals_file', help='Path to signals CSV file')
    parser.add_argument('prices_file', help='Path to prices CSV file')
    parser.add_argument('--max-basket-size', type=int, default=20, help='Maximum stocks per basket')
    parser.add_argument('--start-date', type=str, default=None, help='Start date YYYY-MM-DD')
    parser.add_argument('--end-date', type=str, default=None, help='End date YYYY-MM-DD')

    args = parser.parse_args()

    try:
        results = run_open_to_close_backtest(
            signals_file=args.signals_file,
            prices_file=args.prices_file,
            max_basket_size=args.max_basket_size,
            price_date_start=args.start_date,
            price_date_end=args.end_date
        )
    except Exception as e:
        print(f"❌ ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
