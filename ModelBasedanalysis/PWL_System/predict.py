import pandas as pd
import numpy as np
import xgboost as xgb
from datetime import datetime
from pathlib import Path
import os

def predict_today(custom_open=None):
    # 1. Load Data
    data_files = list(Path('.').glob('QQQ_*.csv'))
    if not data_files:
        print("No QQQ data files found.")
        return
    csv_path = max(data_files, key=os.path.getmtime)
    print(f"Using data from: {csv_path}")

    df = pd.read_csv(csv_path, skiprows=[1])
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    
    cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna()

    # 2. Determine Today vs Context
    # Check if the last row is actually today
    today_date = datetime.now().date()
    last_row_date = df.iloc[-1]['Date'].date()
    
    auto_open = None
    if last_row_date == today_date:
        print(f"Detected data for TODAY ({today_date}) in CSV.")
        auto_open = df.iloc[-1]['Open']
        context_df = df.iloc[:-1] # Use everything EXCEPT today for context
    else:
        print(f"Latest data in CSV is from yesterday ({last_row_date}).")
        context_df = df
    
    last_row = context_df.iloc[-1]
    last_date = last_row['Date']
    last_close = last_row['Close']
    
    # 3. Calculate PWL
    temp_df = context_df.set_index('Date')
    weekly_lows = temp_df['Low'].resample('W').min()
    pwl = weekly_lows.iloc[-1]
    
    print(f"--- QQQ Trader Dashboard ---")
    print(f"Context Date (Last Close): {last_date.date()}")
    print(f"Previous Week Low (PWL): ${pwl:.2f}")
    
    # 4. Handle Open Price
    if custom_open is not None:
        open_price = float(custom_open)
        print(f"Using provided Open Price: ${open_price:.2f}")
    elif auto_open is not None and not np.isnan(auto_open):
        open_price = float(auto_open)
        print(f"Using Auto-detected Open Price: ${open_price:.2f}")
    else:
        try:
            open_price = float(input(f"Enter Today's QQQ Open Price (Date: {today_date}): "))
        except ValueError:
            print("Invalid input. Please enter a numeric price.")
            return

    # 5. Calculate Features based on context_df
    gap_to_pwl_pct = (open_price - pwl) / pwl
    overnight_move_pct = (open_price - last_close) / last_close
    
    # mom_3d using context_df
    mom_3d = (context_df.iloc[-1]['Close'] - context_df.iloc[-4]['Close']) / context_df.iloc[-4]['Close']
    returns = context_df['Close'].pct_change().tail(5)
    volatility_5d = returns.std()

    features_dict = {
        'gap_to_pwl_pct': [gap_to_pwl_pct],
        'overnight_move_pct': [overnight_move_pct],
        'mom_3d': [mom_3d],
        'volatility_5d': [volatility_5d]
    }
    X_input = pd.DataFrame(features_dict)

    # 6. Load Models and Predict
    m1 = xgb.XGBClassifier(); m1.load_model("model_target_1_breach.json")
    m2 = xgb.XGBClassifier(); m2.load_model("model_target_2_fall.json")
    m3 = xgb.XGBClassifier(); m3.load_model("model_target_3_ev.json")

    prob_1 = m1.predict_proba(X_input)[0][1]
    prob_2 = m2.predict_proba(X_input)[0][1]
    prob_3 = m3.predict_proba(X_input)[0][1]

    # 7. Output Results
    print(f"\n--- PROBABILITY REPORT ---")
    print(f"1. Prob of PWL Breach Today: {prob_1:.2%}")
    print(f"2. Prob of 2% Fall (if breached): {prob_2:.2%}")
    print(f"3. Prob of -2% Profit before +2% Stop: {prob_3:.2%}")
    
    if prob_1 > 0.70 and prob_3 > 0.60:
        print("\n[SIGNAL] HIGH CONVICTION SHORT OPPORTUNITY")
    elif prob_1 > 0.50:
        print("\n[SIGNAL] MONITOR FOR BREACH (Moderate Confidence)")
    else:
        print("\n[SIGNAL] NO TRADE - LOW PROBABILITY OF BREACH")

    # 8. Log the Prediction
    log_file = 'daily_predictions_log.csv'
    log_entry = {
        'Date': datetime.now().date(),
        'Open': open_price,
        'PWL': pwl,
        'Gap_Pct': gap_to_pwl_pct,
        'Prob_Breach': prob_1,
        'Prob_Fall': prob_2,
        'Prob_EV': prob_3
    }
    
    log_df = pd.DataFrame([log_entry])
    try:
        if os.path.exists(log_file):
            existing_log = pd.read_csv(log_file)
            updated_log = pd.concat([existing_log, log_df], ignore_index=True)
            updated_log.to_csv(log_file, index=False)
        else:
            log_df.to_csv(log_file, index=False)
    except Exception as e:
        print(f"Logging failed: {e}")
    
    print(f"\nPrediction logged to {log_file}")

if __name__ == "__main__":
    import sys
    o_price = sys.argv[1] if len(sys.argv) > 1 else None
    predict_today(custom_open=o_price)
