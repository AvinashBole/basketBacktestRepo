"""
ENHANCED BASKET PORTFOLIO BACKTEST V2.1 - FIXED EXIT LOGIC

Compatible with Python 3.7+

Fixes:
- Added --enable-stock-level-exit flag to disable individual stock removal
- Fixed target/SL calculations to include stopped stocks at their realized values
- Fixed exit value recording to use actual prices instead of calculated values
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import sys
import argparse
from pathlib import Path

warnings.filterwarnings('ignore')

def run_basket_backtest_v2(
    signals_file,
    prices_file,
    target_pct=1.0,
    stop_loss_pct=2.0,
    max_hold_days=14,
    max_basket_size=20,
    price_date_start=None,
    price_date_end=None,
    enable_stock_level_exit=True,
    output_dir='.'
):
    print("=" * 100)
    print("BASKET PORTFOLIO BACKTEST V2.1 - FIXED EXIT LOGIC")
    print("=" * 100)
    print(f"\nConfiguration:")
    print(f"  Target: +{target_pct}% | Stop Loss: -{stop_loss_pct}% | Max Hold: {max_hold_days} days")
    print(f"  Max Basket Size: {max_basket_size} stocks")
    print(f"  Stock-Level Exit: {'ENABLED' if enable_stock_level_exit else 'DISABLED (basket-only mode)'}")
    print(f"  Output Directory: {output_dir}")

    # 1) Load data
    print("\n[1/8] Loading and validating data...")
    try:
        signals_df = pd.read_csv(signals_file)
        print(f"  ✓ Loaded signals: {len(signals_df)} rows")
    except Exception as e:
        raise Exception(f"Error loading signals file: {str(e)}")

    try:
        prices_df = pd.read_csv(prices_file)
        print(f"  ✓ Loaded prices: {len(prices_df)} rows")
    except Exception as e:
        raise Exception(f"Error loading prices file: {str(e)}")

    req_sig = ['date', 'symbol']
    req_px = ['symbol', 'date', 'close']
    if not all(c in signals_df.columns for c in req_sig):
        raise ValueError(f"Signals file must contain columns: {req_sig}")
    if not all(c in prices_df.columns for c in req_px):
        raise ValueError(f"Prices file must contain columns: {req_px}")

    # 2) Dates: robust parsing
    print("\n[2/8] Processing dates...")
    signals_df['datetime'] = pd.to_datetime(
        signals_df['date'], format='%d-%m-%Y %I:%M %p', errors='coerce'
    )
    na = signals_df['datetime'].isna()
    if na.any():
        signals_df.loc[na, 'datetime'] = pd.to_datetime(
            signals_df.loc[na, 'date'], format='%d-%m-%Y', errors='coerce'
        )
    na = signals_df['datetime'].isna()
    if na.any():
        signals_df.loc[na, 'datetime'] = pd.to_datetime(
            signals_df.loc[na, 'date'], errors='coerce'
        )

    signals_df['trade_ts'] = signals_df['datetime'].dt.normalize()
    prices_df['date'] = pd.to_datetime(prices_df['date'], errors='coerce')
    prices_df['date_norm'] = prices_df['date'].dt.normalize()

    if price_date_start:
        start_ts = pd.to_datetime(price_date_start).normalize()
        prices_df = prices_df[prices_df['date_norm'] >= start_ts]
        print(f"  ✓ Filtered prices from: {price_date_start}")

    if price_date_end:
        end_ts = pd.to_datetime(price_date_end).normalize()
        prices_df = prices_df[prices_df['date_norm'] <= end_ts]
        print(f"  ✓ Filtered prices until: {price_date_end}")

    price_min_ts = prices_df['date_norm'].min()
    price_max_ts = prices_df['date_norm'].max()
    signals_df = signals_df[(signals_df['trade_ts'] >= price_min_ts) & (signals_df['trade_ts'] <= price_max_ts)]

    print(f"  ✓ Price range: {price_min_ts.date()} to {price_max_ts.date()}")
    print(f"  ✓ Signals after filtering: {len(signals_df)} rows, {signals_df['trade_ts'].nunique()} unique dates")

    if len(signals_df) == 0:
        raise ValueError("No signals found within the price data date range!")

    # 3) Baskets
    print("\n[3/8] Creating baskets with size limits...")
    groups = signals_df.groupby('trade_ts')['symbol'].apply(list).reset_index()
    groups.columns = ['trade_ts', 'stocks']
    groups['num_stocks_original'] = groups['stocks'].apply(len)
    groups['stocks'] = groups['stocks'].apply(lambda lst: lst[:max_basket_size])
    groups['num_stocks'] = groups['stocks'].apply(len)

    limited = (groups['num_stocks_original'] > max_basket_size).sum()
    if limited:
        print(f"  ⚠ Limited {limited} baskets to max size {max_basket_size}")

    print(f"  ✓ Created {len(groups)} baskets")
    print(f"  ✓ Avg basket size: {groups['num_stocks'].mean():.1f} stocks")

    # 4) Backtest logic
    print("\n[4/8] Running backtest with FIXED exit logic...")
    all_trades = []
    daily_tracking = []
    skipped_baskets = 0

    for i, row in groups.iterrows():
        trade_ts = row['trade_ts']
        basket_stocks = row['stocks']

        entry_prices_df = prices_df[(prices_df['date_norm'] == trade_ts) &
                                   (prices_df['symbol'].isin(basket_stocks))][['symbol', 'close']]

        if len(entry_prices_df) < max(1, int(len(basket_stocks) * 0.5)):
            skipped_baskets += 1
            continue

        entry_map = dict(zip(entry_prices_df['symbol'], entry_prices_df['close']))
        ordered_stocks = list(entry_map.keys())
        stock_entry_prices_str = "|".join([f"{s}:{entry_map[s]:.2f}" for s in ordered_stocks])

        basket_entry_sum = sum(entry_map.values())
        target_sum = basket_entry_sum * (1 + target_pct / 100)
        stop_sum = basket_entry_sum * (1 - stop_loss_pct / 100)

        # Per-stock exit accounting
        realized_exit_value = {s: None for s in ordered_stocks}
        stock_exit_reason = {s: None for s in ordered_stocks}
        active_stocks = ordered_stocks.copy()

        exit_reason = None
        exit_date = None
        holding_days = 0
        current_dt = trade_ts

        for day in range(1, max_hold_days + 1):
            current_dt = current_dt + pd.Timedelta(days=1)
            while current_dt.weekday() >= 5:
                current_dt = current_dt + pd.Timedelta(days=1)
            current_ts = current_dt.normalize()

            day_prices = prices_df[(prices_df['date_norm'] == current_ts) &
                                   (prices_df['symbol'].isin(active_stocks))][['symbol', 'close']]

            if len(day_prices) == 0:
                continue

            # FIXED: Track stocks that hit individual stop loss
            to_remove = []
            if enable_stock_level_exit:
                for s in active_stocks:
                    px_row = day_prices[day_prices['symbol'] == s]
                    if len(px_row) == 0:
                        continue
                    cur = float(px_row['close'].values[0])
                    ent = float(entry_map[s])
                    ret = (cur - ent) / ent * 100.0

                    if ret <= -stop_loss_pct:
                        # FIXED: Use actual current price, not calculated value
                        realized_exit_value[s] = cur
                        stock_exit_reason[s] = "Stop"
                        to_remove.append(s)

                # Remove stopped stocks from active tracking
                for s in to_remove:
                    active_stocks.remove(s)

                # Check if all stocks stopped
                if len(active_stocks) == 0:
                    exit_reason = "AllStocksStopped"
                    exit_date = current_ts
                    holding_days = day
                    break

            # FIXED: Calculate basket value including stopped stocks at their realized values
            basket_current_sum = 0.0
            for s in ordered_stocks:
                if realized_exit_value[s] is not None:
                    # Use the realized exit value for stopped stocks
                    basket_current_sum += realized_exit_value[s]
                else:
                    # Use current price for active stocks
                    px_row = day_prices[day_prices['symbol'] == s]
                    if len(px_row) > 0:
                        basket_current_sum += float(px_row['close'].values[0])
                    else:
                        # No price data, use entry price
                        basket_current_sum += entry_map[s]

            # Track active sum for reporting
            active_sum = day_prices[day_prices['symbol'].isin(active_stocks)]['close'].sum()

            daily_tracking.append({
                'basket_id': i + 1,
                'entry_date': trade_ts.date(),
                'tracking_date': current_ts.date(),
                'holding_day': day,
                'num_stocks_entry': len(ordered_stocks),
                'num_stocks_active': len(active_stocks),
                'basket_entry_sum': basket_entry_sum,
                'basket_current_sum': float(basket_current_sum),
                'active_sum': float(active_sum),
                'return_pct': (float(basket_current_sum) - basket_entry_sum) / basket_entry_sum * 100.0,
                'stocks_stopped': len(to_remove),
            })

            # FIXED: Check target and stop loss using corrected basket value
            if basket_current_sum >= target_sum:
                exit_reason = "Target"
                exit_date = current_ts
                holding_days = day
                break

            if basket_current_sum <= stop_sum:
                exit_reason = "StopLoss"
                exit_date = current_ts
                holding_days = day
                break

            if day == max_hold_days:
                exit_reason = "MaxHold"
                exit_date = current_ts
                holding_days = day
                break

        # Finalize per-stock exit values and reasons
        if exit_date is None:
            exit_date = trade_ts
            holding_days = 0

        if exit_reason is None:
            exit_reason = "NoFutureData"

        for s in ordered_stocks:
            if realized_exit_value[s] is None:
                # Get final price for active stocks
                hist = prices_df[(prices_df['symbol'] == s) &
                               (prices_df['date_norm'] <= exit_date)].sort_values('date_norm', ascending=False)
                if len(hist) > 0:
                    realized_exit_value[s] = float(hist.iloc[0]['close'])
                    stock_exit_reason[s] = "Market"
                else:
                    realized_exit_value[s] = entry_map[s]
                    stock_exit_reason[s] = "NoFutureData"

        basket_exit_sum = float(sum(realized_exit_value.values()))
        return_pct = (basket_exit_sum - basket_entry_sum) / basket_entry_sum * 100.0

        stock_exit_prices_str = "|".join([f"{s}:{realized_exit_value[s]:.2f}" for s in ordered_stocks])
        stock_exit_reasons_str = "|".join([f"{s}:{stock_exit_reason[s]}" for s in ordered_stocks])

        all_trades.append({
            'basket_id': i + 1,
            'entry_date': trade_ts.date(),
            'exit_date': exit_date.date() if pd.notna(exit_date) else "",
            'num_stocks': len(ordered_stocks),
            'num_stocks_at_exit': len([v for v in realized_exit_value.values() if v is not None]),
            'basket_entry_sum': float(basket_entry_sum),
            'basket_exit_sum': float(basket_exit_sum),
            'return_pct': float(return_pct),
            'holding_days': holding_days,
            'exit_reason': exit_reason,
            'stocks': ", ".join(ordered_stocks),
            'stock_entry_prices': stock_entry_prices_str,
            'stock_exit_prices': stock_exit_prices_str,
            'stock_exit_reasons': stock_exit_reasons_str
        })

    if skipped_baskets:
        print(f"  ⚠ Skipped {skipped_baskets} baskets due to insufficient entry prices")

    trades_df = pd.DataFrame(all_trades)
    daily_df = pd.DataFrame(daily_tracking)

    print(f"  ✓ Completed {len(trades_df)} basket trades")

    if len(trades_df) == 0:
        raise ValueError("No trades were executed. Check date ranges and symbols overlap.")

    print("\n[5/8] Calculating performance statistics...")
    total_trades = len(trades_df)
    win_rate = (trades_df['return_pct'] > 0).mean() * 100.0

    summary_df = pd.DataFrame([{
        'Total_Baskets_Traded': total_trades,
        'Winning_Baskets': int((trades_df['return_pct'] > 0).sum()),
        'Losing_Baskets': int((trades_df['return_pct'] < 0).sum()),
        'Win_Rate_Percent': float(win_rate),
        'Average_Return_Percent': float(trades_df['return_pct'].mean()),
        'Median_Return_Percent': float(trades_df['return_pct'].median()),
        'Best_Return_Percent': float(trades_df['return_pct'].max()),
        'Worst_Return_Percent': float(trades_df['return_pct'].min()),
        'Average_Holding_Days': float(trades_df['holding_days'].mean()),
        'Target_Hit_Count': int((trades_df['exit_reason'] == 'Target').sum()),
        'Stop_Hit_Count': int((trades_df['exit_reason'] == 'StopLoss').sum()),
        'MaxHold_Count': int((trades_df['exit_reason'] == 'MaxHold').sum()),
        'AllStocksStopped_Count': int((trades_df['exit_reason'] == 'AllStocksStopped').sum()),
        'NoFutureData_Count': int((trades_df['exit_reason'] == 'NoFutureData').sum()),
        'Extreme_Losses_Count': int((trades_df['return_pct'] < -(stop_loss_pct + 1)).sum())
    }])

    print("\n[6/8] Performing probability analysis...")
    def pct(n): return float(n) / float(total_trades) * 100.0 if total_trades else 0.0

    prob_df = pd.DataFrame([{
        'Probability_Target_Percent': pct((trades_df['exit_reason'] == 'Target').sum()),
        'Probability_StopLoss_Percent': pct((trades_df['exit_reason'] == 'StopLoss').sum()),
        'Probability_MaxHold_Percent': pct((trades_df['exit_reason'] == 'MaxHold').sum()),
        'Probability_AllStocksStopped_Percent': pct((trades_df['exit_reason'] == 'AllStocksStopped').sum()),
        'Probability_NoFutureData_Percent': pct((trades_df['exit_reason'] == 'NoFutureData').sum()),
        'Avg_Return_When_Target': float(trades_df.loc[trades_df['exit_reason'] == 'Target', 'return_pct'].mean() if (trades_df['exit_reason'] == 'Target').any() else 0.0),
        'Avg_Return_When_StopLoss': float(trades_df.loc[trades_df['exit_reason'] == 'StopLoss', 'return_pct'].mean() if (trades_df['exit_reason'] == 'StopLoss').any() else 0.0),
        'Avg_Return_When_MaxHold': float(trades_df.loc[trades_df['exit_reason'] == 'MaxHold', 'return_pct'].mean() if (trades_df['exit_reason'] == 'MaxHold').any() else 0.0),
        'Avg_Return_When_AllStocksStopped': float(trades_df.loc[trades_df['exit_reason'] == 'AllStocksStopped', 'return_pct'].mean() if (trades_df['exit_reason'] == 'AllStocksStopped').any() else 0.0),
        'Avg_Return_When_NoFutureData': float(trades_df.loc[trades_df['exit_reason'] == 'NoFutureData', 'return_pct'].mean() if (trades_df['exit_reason'] == 'NoFutureData').any() else 0.0),
        'Expected_Value_Per_Trade_Percent': float(trades_df['return_pct'].mean())
    }])

    print("\n[7/8] Calculating monthly performance...")
    trades_df['entry_month'] = pd.to_datetime(trades_df['entry_date']).dt.to_period('M')
    monthly_df = trades_df.groupby('entry_month').agg({
        'basket_id': 'count',
        'return_pct': ['mean', 'sum', 'min', 'max'],
        'holding_days': 'mean'
    }).reset_index()
    monthly_df.columns = ['Month', 'Number_of_Baskets', 'Avg_Return_Percent',
                          'Total_Return_Percent', 'Min_Return_Percent',
                          'Max_Return_Percent', 'Avg_Holding_Days']

    print("\n[8/8] Saving outputs...")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    trades_file = output_path / 'basket_trade_analysis_detailed.csv'
    daily_file = output_path / 'basket_portfolio_daily_tracking.csv'
    summary_file = output_path / 'basket_strategy_summary.csv'
    probability_file = output_path / 'basket_probability_analysis.csv'
    monthly_file = output_path / 'basket_monthly_performance.csv'

    trades_df.to_csv(trades_file, index=False)
    print(f"  ✓ {trades_file}")

    daily_df.to_csv(daily_file, index=False)
    print(f"  ✓ {daily_file}")

    summary_df.to_csv(summary_file, index=False)
    print(f"  ✓ {summary_file}")

    prob_df.to_csv(probability_file, index=False)
    print(f"  ✓ {probability_file}")

    monthly_df.to_csv(monthly_file, index=False)
    print(f"  ✓ {monthly_file}")

    print("\n" + "=" * 100)
    print("✅ BACKTEST COMPLETED SUCCESSFULLY!")
    print("=" * 100)

    return {
        'trades': trades_df,
        'daily_tracking': daily_df,
        'summary': summary_df,
        'probability': prob_df,
        'monthly': monthly_df
    }


def main():
    parser = argparse.ArgumentParser(
        description='Basket Backtest V2.1 - Fixed exit logic with configurable stock-level exits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python basket_backtest_v2_fixed.py signals.csv prices.csv
  python basket_backtest_v2_fixed.py signals.csv prices.csv --enable-stock-level-exit false
  python basket_backtest_v2_fixed.py signals.csv prices.csv --max-basket-size 15
  python basket_backtest_v2_fixed.py signals.csv prices.csv --max-hold-days 10 --stop-loss 1.5
  python basket_backtest_v2_fixed.py signals.csv prices.csv --start-date 2025-03-01 --end-date 2025-10-24
        """
    )

    parser.add_argument('signals_file', help='Path to signals CSV file')
    parser.add_argument('prices_file', help='Path to prices CSV file')
    parser.add_argument('--target', type=float, default=1.0, help='Target profit percentage')
    parser.add_argument('--stop-loss', type=float, default=2.0, help='Stop loss percentage')
    parser.add_argument('--max-hold-days', type=int, default=14, help='Maximum holding days')
    parser.add_argument('--max-basket-size', type=int, default=20, help='Maximum stocks per basket')
    parser.add_argument('--start-date', type=str, default=None, help='Filter start date YYYY-MM-DD')
    parser.add_argument('--end-date', type=str, default=None, help='Filter end date YYYY-MM-DD')
    parser.add_argument('--enable-stock-level-exit', type=str, default='true', 
                       help='Enable individual stock exit on stop loss (true/false, default: true)')
    parser.add_argument('--output-dir', type=str, default='.',
                       help='Directory where output CSV files will be saved')

    args = parser.parse_args()

    # Parse boolean flag
    enable_stock_exit = args.enable_stock_level_exit.lower() in ['true', '1', 'yes', 'y']

    try:
        results = run_basket_backtest_v2(
            signals_file=args.signals_file,
            prices_file=args.prices_file,
            target_pct=args.target,
            stop_loss_pct=args.stop_loss,
            max_hold_days=args.max_hold_days,
            max_basket_size=args.max_basket_size,
            price_date_start=args.start_date,
            price_date_end=args.end_date,
            enable_stock_level_exit=enable_stock_exit,
            output_dir=args.output_dir
        )

        # Always print summary after run
        if results:
            print("\n📊 Quick Summary:")
            print(f"  Total Baskets: {len(results['trades'])}")
            print(f"  Win Rate: {results['summary'].iloc[0]['Win_Rate_Percent']:.2f}%")
            print(f"  Avg Return: {results['summary'].iloc[0]['Average_Return_Percent']:.2f}%")
            print(f"  Expected Value: {results['probability'].iloc[0]['Expected_Value_Per_Trade_Percent']:.4f}%")
            print(f"  Worst Return: {results['summary'].iloc[0]['Worst_Return_Percent']:.2f}%")
            print(f"  Extreme Losses: {results['summary'].iloc[0]['Extreme_Losses_Count']}")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
