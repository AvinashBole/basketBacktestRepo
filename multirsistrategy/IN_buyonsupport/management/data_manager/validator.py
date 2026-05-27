import pandas as pd
import logging
from datetime import datetime

# OSDS-1: Set up logging
logger = logging.getLogger(__name__)

# Constants for strategy requirements
# 14-period Monthly RSI requires at least 14 months of data (~420 days)
MIN_HISTORY_DAYS = 420  
# Data is considered stale if the last update is older than 3 days (accounts for weekends)
MAX_STALE_DAYS = 3      

def validate_integrity(df: pd.DataFrame, symbol: str) -> bool:
    """
    DM-3: Basic integrity check for the OHLCV table.
    Ensures all required columns exist and there are no missing price values.
    """
    if df.empty:
        logger.error(f"Integrity Error: {symbol} - DataFrame is empty.")
        return False
        
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in df.columns for col in required_cols):
        logger.error(f"Integrity Error: {symbol} - Missing mandatory columns.")
        return False
        
    # Check for NaNs in price columns
    if df[['Open', 'High', 'Low', 'Close']].isnull().values.any():
        logger.warning(f"Integrity Warning: {symbol} - Contains null price values.")
        return False

    return True

def validate_sufficiency(df: pd.DataFrame, symbol: str) -> bool:
    """
    Ensures the stock has enough historical data for the Indicator Engine.
    Requires ~420 days of history to compute a stable 14-month RSI.
    """
    df_temp = df.copy()
    df_temp['Date'] = pd.to_datetime(df_temp['Date'])
    
    first_date = df_temp['Date'].min()
    last_date = df_temp['Date'].max()
    history_span = (last_date - first_date).days
    
    if history_span < MIN_HISTORY_DAYS:
        logger.warning(f"Sufficiency Warning: {symbol} only has {history_span} days of history. "
                       f"Need at least {MIN_HISTORY_DAYS} for Monthly RSI.")
        return False
        
    return True

def validate_recency(df: pd.DataFrame, symbol: str) -> bool:
    """
    DM-6: Verifies that the data is up-to-date.
    Ensures the latest record is within the MAX_STALE_DAYS threshold.
    """
    last_date = pd.to_datetime(df['Date']).max()
    days_since_update = (datetime.now() - last_date).days
    
    if days_since_update > MAX_STALE_DAYS:
        logger.error(f"Recency Error: {symbol} data is stale. "
                     f"Last record: {last_date.date()} ({days_since_update} days ago).")
        return False
        
    return True
