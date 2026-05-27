import os
import pandas as pd
import logging
from datetime import datetime, timedelta
from ..config import DATA_DIR, TICKERS_IN, TICKERS_US, STRATEGY_PROFILES, get_domain_data_dir
from .providers import YahooProvider
from .validator import validate_integrity, validate_sufficiency, validate_recency

# OSDS-1: Detailed logging for auditability and developer sanity
logger = logging.getLogger(__name__)

class DataOrchestrator:
    """
    Concept: The Librarian. 
    The central orchestrator for syncing universe data and benchmark indices (DM-1, DM-2).
    """

    def __init__(self, domain="IN"):
        self.provider = YahooProvider()
        self.domain = domain
        self.profile = STRATEGY_PROFILES[self.domain]
        self.tickers = TICKERS_IN if self.domain == "IN" else TICKERS_US
        self.data_dir = get_domain_data_dir(self.domain)
        
    def _get_file_path(self, symbol: str) -> str:
        """Returns the standardized file path for a symbol's CSV, handling varied formats."""
        # 1. Try exact match
        exact_path = os.path.join(self.data_dir, f"{symbol}.csv")
        if os.path.exists(exact_path):
            return exact_path
            
        # 2. Try pattern match (e.g., SYMBOL_2018-01-01_to_2026-05-21.csv)
        import glob
        pattern = os.path.join(self.data_dir, f"{symbol}_*.csv")
        files = glob.glob(pattern)
        if files:
            # Return the most recently updated one
            return max(files, key=os.path.getmtime)
            
        logger.warning(f"Data file not found for {symbol}. Searched in {self.data_dir} with pattern {pattern}")
        return exact_path # Fallback to original

    def _get_last_date(self, symbol: str) -> datetime:
        """
        Procedure: Checks existing inventory to find where history ends.
        Defaults to ~2 years ago if no file exists to satisfy 14-month RSI (DM-2).
        """
        file_path = self._get_file_path(symbol)
        if not os.path.exists(file_path):
            # Satisfy MIN_HISTORY_DAYS (approx 2 years)
            return datetime.now() - timedelta(days=730)
        
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                return datetime.now() - timedelta(days=730)
            return pd.to_datetime(df['Date']).max()
        except Exception as e:
            logger.error(f"Error reading last date for {symbol}: {e}")
            return datetime.now() - timedelta(days=730)

    def sync_symbol(self, symbol: str) -> bool:
        """
        Procedure: Syncs a single symbol incrementally (DM-2).
        Iterated for each symbol in the universe.
        """
        last_date = self._get_last_date(symbol)
        # Start from the day after the last record
        start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        if start_date >= end_date:
            logger.info(f"Skipping {symbol}: Already up to date.")
            return True

        # Fetch incremental data chunk
        new_data = self.provider.fetch_data(symbol, start_date, end_date, self.domain)
        
        if new_data.empty:
            # DM-8: Notification/Logging for missing data
            logger.warning(f"No new data found for {symbol} since {start_date}")
            return False

        # Validate the new data chunk (DM-3)
        if not validate_integrity(new_data, symbol):
            return False

        # Commit to storage
        file_path = self._get_file_path(symbol)
        try:
            # Ensure domain directory exists
            os.makedirs(self.data_dir, exist_ok=True)
            if os.path.exists(file_path):
                # Append without header
                new_data.to_csv(file_path, mode='a', header=False, index=False)
            else:
                # Create new with header
                new_data.to_csv(file_path, index=False)
            logger.info(f"Successfully synced {symbol} from {start_date}")
            return True
        except Exception as e:
            logger.error(f"Failed to commit {symbol} data to CSV: {e}")
            return False

    def sync_universe(self) -> bool:
        """
        Interface: Syncs all tickers in the active universe + benchmark index.
        Output: bool (Success status)
        """
        logger.info(f"Starting {self.domain} Universe Sync...")
        success_count = 0
        
        # 1. Sync Benchmarks first (DM-5)
        self.sync_benchmark()

        # 2. Sync Stock Universe
        for symbol in self.tickers:
            if self.sync_symbol(symbol):
                success_count += 1
        
        logger.info(f"Universe sync complete. Success: {success_count}/{len(self.tickers)}")
        return success_count == len(self.tickers)

    def sync_benchmark(self):
        """Procedure: Specifically updates the primary index for regime analysis (DM-5)."""
        benchmark_symbol = self.profile['benchmark']
        logger.info(f"Updating Benchmark Index: {benchmark_symbol}")
        self.sync_symbol(benchmark_symbol)

    def getOHLCVFromDataStore(self, symbol: str) -> pd.DataFrame:
        """
        Interface for Engine: Provides clean, validated OHLCV data.
        Verifies integrity, sufficiency, and recency (DM-3, DM-6).
        Output: pd.DataFrame
        """
        file_path = self._get_file_path(symbol)
        if not os.path.exists(file_path):
            logger.info(f"Data file for {symbol} not found. Attempting to sync...")
            if not self.sync_symbol(symbol):
                logger.error(f"Failed to sync {symbol} on demand.")
                return pd.DataFrame()
            file_path = self._get_file_path(symbol)
            
        try:
            df = pd.read_csv(file_path)
            # Perform all validation steps
            if (validate_integrity(df, symbol) and 
                validate_sufficiency(df, symbol) and 
                validate_recency(df, symbol)):
                return df
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading OHLCV for {symbol}: {e}")
            return pd.DataFrame()

    def get_index_status(self) -> dict:
        """
        Interface: Returns benchmark price and EMA 200 for regime detection (DM-5).
        Output: dict {symbol, price, ema_200, is_bullish}
        """
        benchmark_symbol = self.profile['benchmark']
        df = self.getOHLCVFromDataStore(benchmark_symbol)
        
        if df.empty:
            logger.error(f"Cannot determine regime: Benchmark data invalid.")
            return {"symbol": benchmark_symbol, "is_bullish": False, "error": "Invalid Data"}
            
        # Calculate EMA 200 for market regime detection
        df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        latest = df.iloc[-1]
        
        return {
            "symbol": benchmark_symbol,
            "price": float(latest['Close']),
            "ema_200": float(latest['ema_200']),
            "is_bullish": bool(latest['Close'] > latest['ema_200'])
        }

if __name__ == "__main__":
    # Debugging entry point
    logging.basicConfig(level=logging.INFO)
    f = DataOrchestrator()
    f.sync_universe()
