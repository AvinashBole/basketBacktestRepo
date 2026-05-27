import logging
import sys
import os

# Ensure we can import from the management package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from management.data_manager.orchestrator import DataOrchestrator
from management.config import ACTIVE_PROFILE

def run_test():
    # Set up basic logging to see the "OSDS-1" logs
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("TestDataManager")

    logger.info(f"Starting Data Manager Test (Active Profile: {ACTIVE_PROFILE})")
    
    orchestrator = DataOrchestrator()

    # 1. Test Single Symbol Sync
    test_symbol = "RELIANCE"
    logger.info(f"--- TEST 1: Syncing {test_symbol} ---")
    sync_success = orchestrator.sync_symbol(test_symbol)
    logger.info(f"Sync Result: {'SUCCESS' if sync_success else 'FAILED'}")

    # 2. Test Data Retrieval and Validation (DM-3, DM-6)
    logger.info(f"--- TEST 2: Retrieving {test_symbol} from DataStore ---")
    df = orchestrator.getOHLCVFromDataStore(test_symbol)
    if not df.empty:
        logger.info(f"Retrieved {len(df)} rows for {test_symbol}")
        logger.info(f"Latest Date: {df['Date'].max()}")
        logger.info(f"History Start: {df['Date'].min()}")
        logger.info("Validation: SUCCESS (Recency and Sufficiency passed)")
    else:
        logger.error("Validation: FAILED (Data might be stale or insufficient)")

    # 3. Test Benchmark Index and Regime Detection (DM-5)
    logger.info("--- TEST 3: Index Status & Regime Detection ---")
    orchestrator.sync_benchmark()
    status = orchestrator.get_index_status()
    if "error" not in status:
        logger.info(f"Benchmark: {status['symbol']}")
        logger.info(f"Current Price: {status['price']:.2f}")
        logger.info(f"200-EMA: {status['ema_200']:.2f}")
        logger.info(f"Market Regime: {'BULLISH' if status['is_bullish'] else 'BEARISH'}")
    else:
        logger.error(f"Index Status Failed: {status.get('error')}")

if __name__ == "__main__":
    run_test()
