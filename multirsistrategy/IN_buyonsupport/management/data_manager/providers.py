import yfinance as yf
import pandas as pd
import logging
import os
from abc import ABC, abstractmethod

# OSDS-1: Detailed logging
logger = logging.getLogger(__name__)

class BaseProvider(ABC):
    """Abstract Base Class for Data Providers (DM-7)."""
    @abstractmethod
    def fetch_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        pass

class YahooProvider(BaseProvider):
    """Primary Data Provider using Yahoo Finance."""
    def fetch_data(self, symbol: str, start_date: str, end_date: str, domain: str = "IN") -> pd.DataFrame:
        """
        Fetches OHLCV data from Yahoo Finance.
        Handles symbol standardization based on domain (DM-7).
        """
        # Standardize symbols based on domain
        # IN: Add .NS if not an index symbol
        # US: Use as is
        if domain == "IN" and "^" not in symbol and ".NS" not in symbol:
            yf_symbol = f"{symbol}.NS"
        else:
            yf_symbol = symbol
        
        try:
            logger.info(f"Fetching {yf_symbol} (Domain: {domain}) from Yahoo Finance ({start_date} to {end_date})")
            # progress=False: Disables yfinance's terminal progress bar to keep log files clean (OSDS-1)
            data = yf.download(yf_symbol, start=start_date, end=end_date, progress=False)
            
            if data.empty:
                logger.warning(f"No data returned for {symbol} from Yahoo")
                # Return empty DataFrame so caller can safely use .empty check without crashing
                return pd.DataFrame()
                
            # Flatten MultiIndex: yfinance sometimes returns symbols nested under price columns
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            # reset_index(): Moves 'Date' from the row index into a regular data column for CSV storage
            data = data.reset_index()
            data['symbol'] = symbol
            
            # Return standardized DataFrame with the specific columns required by the Strategy Engine
            return data[['symbol', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            logger.error(f"Error fetching {symbol} from Yahoo: {e}")
            # Return empty DataFrame on exception to allow universe-loop to continue to next ticker
            return pd.DataFrame()

# Fallback provider logic can be added here in the future (DM-7)
