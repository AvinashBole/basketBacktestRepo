import pandas as pd
import numpy as np
import logging
import sys
import os
import json
from datetime import datetime

# OSDS-1: Detailed logging for auditability and developer sanity
logger = logging.getLogger(__name__)

# Ensure we can import from core/indicators.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.indicators import calculate_rsi, get_ema
from ..config import ACTIVE_PROFILE, STRATEGY_PROFILES, TICKERS_IN, TICKERS_US
from ..data_manager.orchestrator import DataOrchestrator

class IndicatorEngine:
    """
    Concept: The Brain.
    Quantitative processor for Alpha King scoring and regime analysis.
    """
    def __init__(self, orchestrator: DataOrchestrator):
        self.orchestrator = orchestrator
        self.domain = orchestrator.domain
        self.profile = STRATEGY_PROFILES[self.domain]
        self.weights = self.profile['rsi_weights']
        self.elite_thresh = self.profile['elite_thresh']
        # Reports now go into domain-specific subfolders (e.g., management/reports/IN/)
        self.default_report_location = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports', self.domain)
        os.makedirs(self.default_report_location, exist_ok=True)

    def _calculate_symbol_score(self, symbol: str) -> pd.Series:
        """
        Procedure: Computes indicators and scores for a single symbol (IE-1 to IE-5).
        Returns the latest calculated row as a pd.Series (a single row representation).
        """
        df = self.orchestrator.getOHLCVFromDataStore(symbol)
        
        # If data is invalid or missing, return an empty Series to allow loop to continue
        if df.empty:
            return pd.Series()

        try:
            # 1. Pre-processing: Set Date index for resampling (IE-2)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date').set_index('Date')
            
            # 2. EMA and Volume MA Calculation (IE-1, IE-3)
            # EMA helps define trend persistence
            df['ema_9'] = get_ema(df['Close'], 9)
            df['ema_10'] = get_ema(df['Close'], 10)
            df['vol_ma'] = df['Volume'].rolling(window=20).mean()
            
            # 3. Resampling for Multi-Timeframe RSI (IE-2)
            # resample('W'): Weekly, resample('ME'): Month End
            # This aligns daily data to HTF for structural analysis
            df_weekly = df['Close'].resample('W').last().to_frame()
            df_weekly['rsi_weekly'] = calculate_rsi(df_weekly['Close'], 14)
            
            df_monthly = df['Close'].resample('ME').last().to_frame()
            df_monthly['rsi_monthly'] = calculate_rsi(df_monthly['Close'], 14)
            
            df['rsi_daily'] = calculate_rsi(df['Close'], 14)
            
            # 4. Merge MTF RSI back to daily timeframe using merge_asof
            # merge_asof is used to align HTF data (W/M) with daily candles efficiently
            df = pd.merge_asof(df.sort_index(), df_weekly[['rsi_weekly']].sort_index(), left_index=True, right_index=True)
            df = pd.merge_asof(df, df_monthly[['rsi_monthly']].sort_index(), left_index=True, right_index=True)
            
            # 5. Scoring Logic (IE-4)
            # Compute weighted composite score across timeframes
            df['base_score'] = (
                (df['rsi_monthly'] * self.weights['monthly']) + 
                (df['rsi_weekly'] * self.weights['weekly']) + 
                (df['rsi_daily'] * self.weights['daily'])
            )
            df['vol_surge'] = df['Volume'] / df['vol_ma']
            
            df['alpha_score'] = df['base_score']
            
            # df.loc[rows, columns]: Vectorized update of rows meeting condition
            # Volume Bonus: +25 if current volume > 1.5x of the 20-day average
            df.loc[df['vol_surge'] > 1.5, 'alpha_score'] += 25
            
            # 6. Rocket Signal [India Only] (IE-5)
            df['is_rocket'] = False
            if self.profile.get('rocket_enabled', False):
                # Rocket: Monthly/Weekly RSI > 40 AND Volume Surge > 2.0
                df['is_rocket'] = (df['rsi_weekly'] > 40) & (df['rsi_monthly'] > 40) & (df['vol_surge'] > 2.0)
                # Rocket Bonus: +30 points to Alpha Score
                df.loc[df['is_rocket'] == True, 'alpha_score'] += 30
            
            # 7. Entry Signal Logic
            # HTF health: Monthly/Weekly > 50. Confirmed by Price > EMA9.
            df['bullish_htf'] = (df['rsi_weekly'] > 50) & (df['rsi_monthly'] > 50)
            
            # Entry Signal = ROCKET || (HTF_BULLISH && PRICE > EMA9)
            df['signal'] = df['is_rocket'] | (df['bullish_htf'] & (df['Close'] > df['ema_9']))
            
            # 8. Extract the last row (most recent data point) for the Action Report
            latest = df.iloc[-1].copy()
            logger.debug(f"Scored {symbol}: Alpha={latest['alpha_score']:.1f}")
            return latest
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol}: {e}")
            return pd.Series()

    def compute_alpha_scores(self, symbols: list[str] = None, generateReport: bool = True, reportLocation: str = None) -> pd.DataFrame:
        """
        Interface: Main loop to compute scores for universe or targeted list (IE-6).
        Procedure: Iterates over each symbol, calls _calculate_symbol_score individually.
        Output: pd.DataFrame (latest stats for each stock)
        """
        target_list = symbols if symbols else (TICKERS_IN if self.domain == "IN" else TICKERS_US)
        logger.info(f"Computing Alpha Scores for {len(target_list)} symbols in {self.domain}...")
        
        results = []
        for symbol in target_list:
            latest_row = self._calculate_symbol_score(symbol)
            if not latest_row.empty:
                latest_row['symbol'] = symbol
                results.append(latest_row)
                
        if not results:
            logger.warning("Scoring complete, but no valid symbol data was processed.")
            return pd.DataFrame()
            
        df_scored = pd.DataFrame(results).sort_values('alpha_score', ascending=False)
        
        if generateReport:
            location = reportLocation or self.default_report_location
            os.makedirs(location, exist_ok=True)
            date_str = datetime.now().strftime('%Y-%m-%d')
            report_path = os.path.join(location, f"elite_scores_{date_str}.csv")
            df_scored.to_csv(report_path, index=False)
            logger.info(f"Alpha scores report saved to: {report_path}")
            
        return df_scored

    def generate_signals(self, df_scored: pd.DataFrame, generateReport: bool = True, reportLocation: str = None) -> dict:
        """
        Interface: Extracts actionable signal lists from scored data.
        """
        if df_scored.empty:
            return {"rockets": [], "entries": [], "top_candidates": []}
            
        df_signals = df_scored[df_scored['signal'] == True]
        
        signal_dict = {
            "rockets": df_signals[df_signals['is_rocket'] == True]['symbol'].tolist(),
            "entries": df_signals['symbol'].tolist(),
            "top_candidates": df_signals.head(10)[['symbol', 'alpha_score']].to_dict('records')
        }
        
        if generateReport:
            location = reportLocation or self.default_report_location
            os.makedirs(location, exist_ok=True)
            date_str = datetime.now().strftime('%Y-%m-%d')
            report_path = os.path.join(location, f"signals_{date_str}.json")
            with open(report_path, 'w') as f:
                json.dump(signal_dict, f, indent=4)
            logger.info(f"Signals report saved to: {report_path}")
            
        return signal_dict

    def assess_market_regime(self, df_scored: pd.DataFrame) -> dict:
        """
        Interface: Regime analysis and dynamic capacity calculation (SE-2).
        Output: dict {elite_count, max_slots, defensive_mode, benchmark_status}
        """
        index_status = self.orchestrator.get_index_status()
        
        if df_scored.empty:
            return {"elite_count": 0, "max_slots": 5, "defensive_mode": True}

        # Count symbols above the defined Elite Threshold
        elite_count = len(df_scored[df_scored['alpha_score'] >= self.elite_thresh])
        
        # Scaling Logic: Standard linear range between 5 and 15
        max_slots = max(5, min(15, elite_count))
        
        # Defensive Mode: Force capacity to minimum if Benchmark is below its 200-EMA
        defensive_mode = not index_status.get('is_bullish', True)
        if defensive_mode:
            logger.warning(f"Market Regime: BEARISH (Index below EMA200). Activating Defensive Mode.")
            max_slots = 5
            
        return {
            "elite_count": elite_count,
            "max_slots": max_slots,
            "defensive_mode": defensive_mode,
            "benchmark_status": index_status
        }
