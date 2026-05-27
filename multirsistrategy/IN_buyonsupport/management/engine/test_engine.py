import logging
import sys
import os
import pandas as pd

# Ensure we can import from the management package
# We are in management/engine/test_engine.py
# Root is 3 levels up
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from management.data_manager.orchestrator import DataOrchestrator
from management.engine.engine import IndicatorEngine
from management.config import ACTIVE_PROFILE

def run_test():
    # OSDS-1: Detailed logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("TestEngine")

    logger.info(f"Starting Engine Test (Active Profile: {ACTIVE_PROFILE})")
    
    orchestrator = DataOrchestrator()
    engine = IndicatorEngine(orchestrator)

    # Define a subset of stocks for rapid testing
    subset = ["RELIANCE", "ABB", "ADANIENT", "AARTIIND", "AXISBANK"]
    
    # 1. Sync subset first to ensure we have data
    logger.info(f"--- PRE-TEST: Syncing subset {subset} ---")
    for sym in subset:
        orchestrator.sync_symbol(sym)
    orchestrator.sync_benchmark()

    # 2. Compute Alpha Scores (IE-6: Targeted list processing)
    logger.info("--- TEST 1: Computing Alpha Scores for Subset ---")
    df_scored = engine.compute_alpha_scores(symbols=subset)
    
    if not df_scored.empty:
        # Display formatted results
        cols_to_show = ['symbol', 'alpha_score', 'rsi_monthly', 'rsi_weekly', 'rsi_daily', 'vol_surge', 'is_rocket', 'signal']
        print("\n" + "="*80)
        print(f" ALPHA SCORE RESULTS ({ACTIVE_PROFILE} PROFILE)")
        print("="*80)
        print(df_scored[cols_to_show].to_string(index=False))
        print("="*80 + "\n")
    else:
        logger.error("Scoring FAILED: No data returned.")
        return

    # 3. Generate Actionable Signals
    logger.info("--- TEST 2: Generating Actionable Signals ---")
    signals = engine.generate_signals(df_scored)
    print(f"Rockets Detected: {', '.join(signals['rockets']) if signals['rockets'] else 'None'}")
    print(f"Entry Candidates: {', '.join(signals['entries']) if signals['entries'] else 'None'}")
    print("-" * 40)

    # 4. Assess Market Regime
    logger.info("--- TEST 3: Market Regime & Capacity Check ---")
    regime = engine.assess_market_regime(df_scored)
    print(f"Elite Count: {regime['elite_count']}")
    print(f"Suggested Max Slots: {regime['max_slots']}")
    print(f"Defensive Mode Active: {regime['defensive_mode']}")
    print(f"Index Bullish: {regime['benchmark_status']['is_bullish']}")
    print("="*40 + "\n")

if __name__ == "__main__":
    run_test()
