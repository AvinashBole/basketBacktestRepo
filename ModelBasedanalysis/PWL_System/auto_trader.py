import os
import subprocess
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
SYMBOL = "QQQ"
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR
DOWNLOADER_PATH = BASE_DIR.parent.parent / "us_data_downloader.py"
MASTER_DATA_FILE = DATA_DIR / "mvp_features_targets.csv"

def run_cmd(cmd):
    print(f"Executing: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.stdout

def sync_data():
    print("--- Step 1: Syncing Data ---")
    today = datetime.now().strftime("%Y-%m-%d")
    start_date = "2018-01-01"
    
    # Update the downloader's end_date by modifying the script or just calling its function if possible.
    # Since it is a standalone script, we will run it via python -c to call the specific function.
    py_cmd = f"python3 -c \"import sys; sys.path.append('{DOWNLOADER_PATH.parent}'); from us_data_downloader import download_us_symbol; download_us_symbol('{SYMBOL}', '{start_date}', '{today}', output_dir='{DATA_DIR}')\""
    run_cmd(py_cmd)
    
    # Find the newly downloaded file
    files = list(DATA_DIR.glob(f"{SYMBOL}_{start_date}_to_*.csv"))
    if not files:
        print("No downloaded files found.")
        return None
    
    latest_file = max(files, key=os.path.getmtime)
    print(f"Latest raw data: {latest_file.name}")
    return latest_file

def process_data(raw_file):
    print("\n--- Step 2: Processing Data ---")
    # We use the existing logic from step1_2_prepare_data.py but modified to check if we need update
    from step1_2_prepare_data import prepare_data
    
    # For MVP, we'll just re-prepare the whole thing to ensure consistency, 
    # but we could optimize for incremental processing later.
    new_processed_df = prepare_data(str(raw_file))
    new_processed_df.to_csv(MASTER_DATA_FILE, index=False)
    print(f"Master data updated: {MASTER_DATA_FILE}")

def train_if_needed():
    print("\n--- Step 3: Training Models ---")
    # In a real system, we'd check if we have enough new data. 
    # For now, we retrain to ensure the 2026 data is included.
    from train_models import train_and_save_models
    train_and_save_models(str(MASTER_DATA_FILE))

def get_prediction(open_price=None):
    print("\n--- Step 4: Final Prediction ---")
    raw_df = pd.read_csv(MASTER_DATA_FILE)
    last_date_str = raw_df.iloc[-1]['Date']
    print(f"Latest data in system: {last_date_str}")
    
    cmd = ["python3", "predict.py"]
    if open_price:
        cmd.append(str(open_price))
    
    # Run with cwd set to the directory containing predict.py
    subprocess.run(cmd, cwd=str(BASE_DIR))

if __name__ == "__main__":
    import sys
    arg_open = sys.argv[1] if len(sys.argv) > 1 else None
    
    raw_file = sync_data()
    if raw_file:
        process_data(raw_file)
        train_if_needed()
        get_prediction(arg_open)
