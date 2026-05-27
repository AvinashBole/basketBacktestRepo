import pandas as pd
import numpy as np
import os
import glob
from buyonsupport.core.indicators import calculate_rsi, get_ema

def load_universe(data_path='data/*.csv'):
    """
    Loads US stock data and calculates Alpha King Score 3.2.
    Weights: 40% Monthly, 40% Weekly, 20% Daily.
    """
    files = glob.glob(data_path)
    stocks = {}
    for f in files:
        try:
            df = pd.read_csv(f, skiprows=[1])
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
            
            # ALPHA KING SCORE 3.2
            df['alpha_score'] = (df['rsi_monthly'] * 0.4) + (df['rsi_weekly'] * 0.4) + (df['rsi_daily'] * 0.2)
            df['vol_surge'] = df['Volume'] / df['vol_ma']
            df.loc[df['vol_surge'] > 1.5, 'alpha_score'] += 25
            
            df['bullish_htf'] = (df['rsi_weekly'] > 40) & (df['rsi_monthly'] > 40)
            df['signal'] = (df['bullish_htf'] & (df['rsi_weekly'] > 50) & (df['Close'] > df['ema_9']))
            
            stocks[symbol] = df
        except: continue
    return stocks

def run_breathing_portfolio(stocks, initial_capital=100000, elite_thresh=100, swap_hurdle=20):
    """
    Dynamic Portfolio Simulation with 'Breathing' Basket Size (5-15 Slots).
    """
    all_dates = sorted(pd.concat([df.index.to_series() for df in stocks.values()]).unique())
    positions = {} # {symbol: {entry_date, entry_price, peak_price, initial_pos_value}}
    current_cash = initial_capital
    ledger = []
    
    for current_date in all_dates:
        removals = []
        additions = []
        
        # 0. MARKET BREADTH SENSING (The 'Breathing' Logic)
        breadth_count = 0
        for s, df in stocks.items():
            if current_date in df.index and df.loc[current_date, 'alpha_score'] > 100:
                breadth_count += 1
        
        if breadth_count > 30: max_slots = 15     # Expand in Broad Bull
        elif breadth_count < 5: max_slots = 5     # Contract in Narrow/Bear
        else: max_slots = 10                       # Standard
        
        # 1. Update/Exit
        symbols_to_exit = []
        for symbol, pos in positions.items():
            df = stocks[symbol]
            if current_date not in df.index: continue
            row = df.loc[current_date]
            pos['peak_price'] = max(pos['peak_price'], row['High'])
            
            pnl_pct = (row['Close'] - pos['entry_price']) / pos['entry_price'] * 100
            current_pos_val = pos['initial_pos_value'] * (1 + pnl_pct/100)
            
            exit_trigger = False
            reason = ""
            if row['High'] < row['ema_10']: exit_trigger, reason = True, "High < EMA 10"
            elif row['Low'] < pos['peak_price'] * 0.75: exit_trigger, reason = True, "Disaster Stop (25%)"
            elif row['rsi_weekly'] < 40 or row['rsi_monthly'] < 40: exit_trigger, reason = True, "Context Loss"
            
            if exit_trigger:
                current_cash += current_pos_val
                symbols_to_exit.append(symbol)
                removals.append(f"{symbol}[Out,PnL:{pnl_pct:.1f}%,Reason:{reason}]")
        
        for s in symbols_to_exit: del positions[s]
        
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
                current_scores = [{'sym': s, 'score': stocks[s].loc[current_date, 'alpha_score']} for s in active_holdings]
                weakest = min(current_scores, key=lambda x: x['score'])
                best_cand = candidates[0]
                
                if best_cand['score'] >= elite_thresh and best_cand['score'] > weakest['score'] + swap_hurdle:
                    row_sell = stocks[weakest['sym']].loc[current_date]
                    pnl_sell = (row_sell['Close'] / positions[weakest['sym']]['entry_price']) - 1
                    current_cash += positions[weakest['sym']]['initial_pos_value'] * (1 + pnl_sell)
                    removals.append(f"{weakest['sym']}[Swap-Out, PnL:{pnl_sell*100:.1f}%]")
                    del positions[weakest['sym']]

        # 4. Entry Logic
        for cand in candidates:
            if len(positions) < max_slots and current_cash > 0:
                symbol = cand['symbol']
                row = stocks[symbol].loc[current_date]
                pos_size_dollars = current_cash / (max_slots - len(positions))
                positions[symbol] = {
                    'entry_date': current_date,
                    'entry_price': row['Close'],
                    'peak_price': row['Close'],
                    'initial_pos_value': pos_size_dollars
                }
                current_cash -= pos_size_dollars
                additions.append(symbol)

        # 5. Equity Tracking
        open_pos_val = sum([pos['initial_pos_value'] * (stocks[s].loc[current_date, 'Close'] / pos['entry_price']) for s, pos in positions.items() if current_date in stocks[s].index])
        total_equity = current_cash + open_pos_val
        
        if len(positions) > 0 or removals or additions:
            ledger.append({
                'Date': current_date.strftime('%Y-%m-%d'),
                'Total_Equity': f"${total_equity:,.2f}",
                'Cumulative_Profit': f"${(total_equity - initial_capital):,.2f}",
                'Basket_Size': len(positions),
                'Max_Slots': max_slots,
                'Additions': ", ".join(additions),
                'Removals': ", ".join(removals),
                'Top_Candidates': ", ".join([f"{c['symbol']}({c['score']:.0f})" for c in candidates[:5]]),
                'Basket_Breakdown': " | ".join([f"{s}[In:{pos['entry_price']:.1f},Cur:{stocks[s].loc[current_date, 'Close']:.1f},PnL:{(stocks[s].loc[current_date, 'Close']/pos['entry_price']-1)*100:.1f}%]" for s, pos in positions.items() if current_date in stocks[s].index])
            })
            
    return pd.DataFrame(ledger)
