import logging
import sys
import os
import json

# Ensure we can import from the management package
# Root is 3 levels up
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from management.portfolio.portfolio_manager import PortfolioManager
from management.config import STATE_FILE

def run_test():
    # OSDS-1: Detailed logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("TestPortfolio")

    # Clean up existing state file for a clean test
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        logger.info("Removed existing state file for clean test.")

    logger.info("Starting Portfolio Manager Test...")
    pm = PortfolioManager()

    # 1. Test Position Addition (PT-1, PT-2)
    logger.info("--- TEST 1: Adding Positions ---")
    pm.add_position("RELIANCE", 2500.0, 10, "2026-05-24")
    pm.add_position("ABB", 8000.0, 5, "2026-05-24")
    
    cash = pm.get_cash()
    positions = pm.get_active_positions()
    logger.info(f"Current Cash: {cash}")
    logger.info(f"Active Positions: {list(positions.keys())}")
    
    if len(positions) == 2 and cash == (100000.0 - (2500*10 + 8000*5)):
        logger.info("Position Addition: SUCCESS")
    else:
        logger.error("Position Addition: FAILED")

    # 2. Test Peak Price Update (PT-2)
    logger.info("--- TEST 2: Updating Peak Price ---")
    # RELIANCE goes up to 2600
    pm.update_peak("RELIANCE", 2600.0)
    # ABB goes down (should NOT update peak)
    pm.update_peak("ABB", 7500.0)
    
    pos = pm.get_active_positions()
    logger.info(f"RELIANCE Peak: {pos['RELIANCE']['peak_price']}")
    logger.info(f"ABB Peak: {pos['ABB']['peak_price']}")
    
    if pos['RELIANCE']['peak_price'] == 2600.0 and pos['ABB']['peak_price'] == 8000.0:
        logger.info("Peak Update Logic: SUCCESS")
    else:
        logger.error("Peak Update Logic: FAILED")

    # 3. Test Reconciliation (PT-1)
    logger.info("--- TEST 3: Broker Reconciliation ---")
    mock_broker_data = [
        {"symbol": "RELIANCE", "qty": 10},
        {"symbol": "ABB", "qty": 5}
    ]
    discrepancies = pm.reconcile_with_broker(mock_broker_data)
    if not discrepancies:
        logger.info("Reconciliation (Match): SUCCESS")
    
    mock_bad_data = [
        {"symbol": "RELIANCE", "qty": 10},
        {"symbol": "INFY", "qty": 20} # Extra in broker
    ]
    discrepancies = pm.reconcile_with_broker(mock_bad_data)
    logger.info(f"Detected Discrepancies: {discrepancies}")
    if len(discrepancies) == 2: # Should miss ABB and find extra INFY
        logger.info("Reconciliation (Mismatch detection): SUCCESS")

    # 4. Test Persistence
    logger.info("--- TEST 4: Persistence Check ---")
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            logger.info(f"State file exists and has {len(data['positions'])} positions.")
            logger.info("Persistence: SUCCESS")

    # 5. Test Position Removal
    logger.info("--- TEST 5: Removing Position ---")
    pm.remove_position("RELIANCE", 2700.0, "2026-05-25", reason="EMA10 Breach")
    logger.info(f"Final Cash: {pm.get_cash()}")
    if "RELIANCE" not in pm.get_active_positions():
        logger.info("Position Removal: SUCCESS")

if __name__ == "__main__":
    run_test()
