import pandas as pd
import numpy as np
import os
import glob
import sys

# Ensure we can import indicators from the IN_buyonsupport directory
sys.path.append('.')
from core.indicators import calculate_rsi, get_ema

def load_universe(data_path='data/*.csv'):
    files = glob.glob(data_path)
    stocks = {}
    print(f"Loading {len(files)} Indian stocks...")
    for f in files:
        try:
            df = pd.read_csv(f)
            if df.empty: continue
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date').set_index('Date')
            symbol = df['symbol'].iloc[0]
            
            df['ema_9'] = get_ema(df['Close'], 9)
            df['ema_10'] = get_ema(df['Close'], 10)
            df['vol_ma'] = df['Volume'].rolling(window=20).mean()
            
            df_weekly = df['Close'].resample('W').last().to_frame()
            df_weekly['rsi_weekly'] = calculate_rsi(df_weekly['Close'], 14)
            df_monthly = df['Close'].resample('ME').last().to_frame()
            df_monthly['rsi_monthly'] = calculate_rsi(df_monthly['Close'], 14)
            df['rsi_daily'] = calculate_rsi(df['Close'], 14)
            
            df = pd.merge_asof(df.sort_index(), df_weekly[['rsi_weekly']].sort_index(), left_index=True, right_index=True)
            df = pd.merge_asof(df, df_monthly[['rsi_monthly']].sort_index(), left_index=True, right_index=True)
            
            # ALPHA KING 3.1 LOGIC
            df['base_score'] = (df['rsi_monthly'] * 0.5) + (df['rsi_weekly'] * 0.3) + (df['rsi_daily'] * 0.2)
            df['vol_surge'] = df['Volume'] / df['vol_ma']
            
            # THE CORRECT ROCKET definition: (RSI > 40 and Vol Surge)
            df['is_rocket'] = (df['rsi_weekly'] > 40) & (df['rsi_monthly'] > 40) & (df['vol_surge'] > 2.0)
            
            # Scoring
            df['alpha_score'] = df['base_score']
            df.loc[df['vol_surge'] > 1.5, 'alpha_score'] += 25
            df.loc[df['is_rocket'], 'alpha_score'] += 30
            
            # Entry Signals
            df['bullish_htf'] = (df['rsi_weekly'] > 50) & (df['rsi_monthly'] > 50)
            df['signal'] = df['is_rocket'] | (df['bullish_htf'] & (df['Close'] > df['ema_9']))
            
            stocks[symbol] = df
        except: continue
    return stocks

def run_elite_scaling_backtest(stocks, initial_capital=100000, elite_thresh=130, swap_hurdle=20):
    all_dates = sorted(pd.concat([df.index.to_series() for df in stocks.values()]).unique())
    positions = {}
    current_cash = initial_capital
    ledger = []
    
    for current_date in all_dates:
        removals = []
        additions = []
        
        scores_pool = [df.loc[current_date, 'alpha_score'] for df in stocks.values() if current_date in df.index]
        elite_count = sum(1 for s in scores_pool if s >= elite_thresh)
        max_slots = max(5, min(15, elite_count))
        
        # 1. Exit
        to_exit = []
        for symbol, pos in positions.items():
            df = stocks[symbol]
            if current_date not in df.index: continue
            row = df.loc[current_date]
            pos['peak'] = max(pos['peak'], row['High'])
            pnl_pct = (row['Close'] - pos['entry_price']) / pos['entry_price'] * 100
            
            exit_trigger = False
            reason = ""
            if row['High'] < row['ema_10']: exit_trigger, reason = True, "EMA10"
            elif row['Low'] < pos['peak'] * 0.75: exit_trigger, reason = True, "Stop25"
            elif row['rsi_weekly'] < 40 or row['rsi_monthly'] < 40: exit_trigger, reason = True, "Context"
            
            if exit_trigger:
                exit_val = pos['initial_val'] * (1 + pnl_pct/100)
                current_cash += exit_val
                removals.append(f"{symbol}[Out,PnL:{pnl_pct:.1f}%,Reason:{reason}]")
                to_exit.append(symbol)
        for s in to_exit: del positions[s]
        
        # 2. Candidate Selection
        candidates = []
        for symbol, df in stocks.items():
            if current_date in df.index and df.loc[current_date, 'signal'] and symbol not in positions:
                candidates.append({'symbol': symbol, 'score': df.loc[current_date, 'alpha_score']})
        candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)

        # 3. Swap Engine
        if len(positions) >= max_slots and candidates:
            active_holdings = [s for s in positions.keys() if current_date in stocks[s].index]
            if active_holdings:
                current_scores = [{'s': s, 'score': stocks[s].loc[current_date, 'alpha_score']} for s in active_holdings]
                weakest = min(current_scores, key=lambda x: x['score'])
                best_cand = candidates[0]
                if best_cand['score'] >= elite_thresh and best_cand['score'] > weakest['score'] + swap_hurdle:
                    row_sell = stocks[weakest['s']].loc[current_date]
                    pnl_s = (row_sell['Close'] / positions[weakest['s']]['entry_price'] - 1) * 100
                    current_cash += positions[weakest['s']]['initial_val'] * (1 + pnl_s/100)
                    removals.append(f"{weakest['s']}[Swap-Out,PnL:{pnl_s:.1f}%]")
                    del positions[weakest['s']]

        # 4. Entry
        for cand in candidates:
            if len(positions) < max_slots and current_cash > 0:
                symbol = cand['symbol']
                row = stocks[symbol].loc[current_date]
                size = current_cash / (max_slots - len(positions))
                positions[symbol] = {
                    'entry_date': current_date,
                    'entry_price': row['Close'],
                    'peak': row['Close'],
                    'initial_val': size
                }
                current_cash -= size
                additions.append(symbol)

        open_pos_val = sum([pos['initial_val'] * (stocks[s].loc[current_date, 'Close'] / pos['entry_price']) for s, pos in positions.items() if current_date in stocks[s].index])
        total_equity = current_cash + open_pos_val
        
        if len(positions) > 0 or removals or additions:
            breakdown = []
            for s, pos in positions.items():
                if current_date in stocks[s].index:
                    cur_p = stocks[s].loc[current_date, 'Close']
                    pnl = (cur_p / pos['entry_price'] - 1) * 100
                    breakdown.append(f"{s}[In:{pos['entry_price']:.1f},Cur:{cur_p:.1f},PnL:{pnl:.1f}%]")
            
            ledger.append({
                'Date': current_date.strftime('%Y-%m-%d'),
                'Total_Equity': f"${total_equity:,.2f}",
                'Cumulative_Profit': f"${(total_equity - initial_capital):,.2f}",
                'Basket_Size': len(positions),
                'Max_Slots': max_slots,
                'Additions': ", ".join(additions),
                'Removals': ", ".join(removals),
                'Top_Candidates': ", ".join([f"{c['symbol']}({c['score']:.0f})" for c in candidates[:5]]),
                'Basket_Breakdown': " | ".join(breakdown)
            })
            
    return pd.DataFrame(ledger)

if __name__ == "__main__":
    print("Initializing Elite Scaling v4 (MATCHING ALPHA KING 130 + Linear Scaling, INDIA)...")
    stocks = load_universe()
    df_ledger = run_elite_scaling_backtest(stocks)
    
    os.makedirs('results_v3', exist_ok=True)
    output_path = 'results_v3/elite_scaling_v4_ledger_IN.csv'
    df_ledger.to_csv(output_path, index=False)
    
    print("\n" + "="*40)
    print("ELITE SCALING V4 INDIA COMPLETE")
    print(f"Final Equity: {df_ledger['Total_Equity'].iloc[-1]}")
    print(f"Detailed Ledger: {output_path}")
    print("="*40)
