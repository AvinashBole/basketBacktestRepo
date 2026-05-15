import pandas as pd
import numpy as np

def prepare_data(file_path):
    print(f"Reading {file_path}...")
    df = pd.read_csv(file_path, skiprows=[1])
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    
    cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna()
    print(f"Initial daily rows: {len(df)}")

    # Calculate Weekly Lows
    # resample('W') groups by week ending Sunday.
    # We want the 'Low' of that week.
    weekly_lows = df.set_index('Date')['Low'].resample('W').min().rename('PWL')
    
    # Shift so that THIS week's PWL is the MIN LOW of the PREVIOUS week.
    weekly_lows = weekly_lows.shift(1)
    
    # Merge strategy:
    # Since weekly_lows index is Sunday, we need to map it to the next week's trading days.
    # We'll merge_asof, which is perfect for this.
    df = df.sort_values('Date')
    weekly_lows = weekly_lows.reset_index().sort_values('Date')
    
    # merge_asof will take each 'Date' in df and find the last 'Date' in weekly_lows 
    # that is less than or equal to it.
    df = pd.merge_asof(df, weekly_lows, on='Date', direction='backward')
    
    print(f"Rows after merge: {len(df)}")
    df = df.dropna(subset=['PWL']).copy()
    print(f"Rows with PWL: {len(df)}")

    # Feature Engineering
    df['gap_to_pwl_pct'] = (df['Open'] - df['PWL']) / df['PWL']
    df['overnight_move_pct'] = (df['Open'] - df['Close'].shift(1)) / df['Close'].shift(1)
    df['mom_3d'] = (df['Close'].shift(1) - df['Close'].shift(4)) / df['Close'].shift(4)
    df['volatility_5d'] = df['Close'].pct_change().shift(1).rolling(5).std()

    # Target Labeling
    X_FALL = 0.02
    Y_CANDLES = 5
    Z_GAIN = 0.02

    df['target_1_breach'] = (df['Low'] <= df['PWL']).astype(int)

    t2_labels = []
    t3_labels = []

    for i in range(len(df)):
        if df.iloc[i]['target_1_breach'] == 1:
            pwl = df.iloc[i]['PWL']
            # Look at future (including today's close if breach happened during day)
            # Actually, let's look from TOMORROW for Target 2/3 to keep it clean.
            future_window = df.iloc[i + 1 : i + 1 + Y_CANDLES]
            
            if len(future_window) == 0:
                t2_labels.append(np.nan)
                t3_labels.append(np.nan)
                continue
            
            target_price = pwl * (1 - X_FALL)
            stop_price = pwl * (1 + Z_GAIN)
            
            # Target 2
            t2_success = (future_window['Low'] <= target_price).any()
            t2_labels.append(int(t2_success))
            
            # Target 3
            fall_idx = np.where(future_window['Low'] <= target_price)[0]
            gain_idx = np.where(future_window['High'] >= stop_price)[0]
            
            first_fall = fall_idx[0] if len(fall_idx) > 0 else 999
            first_gain = gain_idx[0] if len(gain_idx) > 0 else 999
            
            if first_fall == 999 and first_gain == 999:
                t3_labels.append(np.nan)
            else:
                t3_labels.append(int(first_fall < first_gain))
        else:
            t2_labels.append(np.nan)
            t3_labels.append(np.nan)

    df['target_2_fall'] = t2_labels
    df['target_3_ev'] = t3_labels

    return df

if __name__ == "__main__":
    processed_df = prepare_data('QQQ_2018-01-01_to_2026-05-14.csv')
    show_cols = ['Date', 'Open', 'Low', 'PWL', 'gap_to_pwl_pct', 'target_1_breach', 'target_2_fall', 'target_3_ev']
    print("\n--- MVP Data Preview ---")
    print(processed_df[show_cols].head(10))
    print("\n--- Breach Stats ---")
    print(f"Total Breaches: {processed_df['target_1_breach'].sum()}")
    print(processed_df[processed_df['target_1_breach'] == 1][show_cols].dropna().head(10))
    processed_df.to_csv('mvp_features_targets.csv', index=False)
