import argparse
import logging
from .portfolio.portfolio_manager import PortfolioManager
from .data_manager.orchestrator import DataOrchestrator
from .engine.engine import IndicatorEngine
from .config import ACTIVE_PROFILE

# OSDS-1: Detailed logging
logger = logging.getLogger(__name__)

def initialize_ledger(pm, interactive=True):
    """
    Procedure: Display ledger, prompt for validation, and reconcile if needed.
    """
    print("" + "="*50)
    print(" ESMS INITIALIZATION: LEDGER VALIDATION")
    print("="*50)
    positions = pm.get_active_positions()
    currency = "₹" if ACTIVE_PROFILE == "IN" else "$"
    print(f"Persisted Cash: {currency}{pm.get_cash():,.2f}")
    print("Persisted Positions:")
    for sym, data in positions.items():
        print(f"  {sym}: {data['qty']}")
    print("="*50)
    
    if not interactive:
        logger.info("Running in non-interactive mode. Skipping validation.")
        return

    confirm = input("Do these holdings match your broker? (y/n): ").lower()
    
    if confirm == 'y':
        return
    else:
        # Manual entry mode
        print("Enter your actual broker holdings (Symbol,Qty). Type 'done' when finished:")
        broker_data = []
        while True:
            entry = input("> ")
            if entry.lower() == 'done':
                break
            try:
                sym, qty = entry.split(',')
                broker_data.append({"symbol": sym.strip().upper(), "qty": int(qty)})
            except ValueError:
                print("Invalid format. Use: SYMBOL,QTY")
        
        # Reconcile and prompt update
        discrepancies = pm.reconcile_with_broker(broker_data)
        if discrepancies:
            print("Discrepancies found:", discrepancies)
            update = input("Update ledger to match broker? (y/n): ").lower()
            if update == 'y':
                # Simplified manual update for cash/positions logic
                new_cash = float(input("Enter current total cash: "))
                new_positions = {h['symbol']: {"qty": h['qty'], "entry_price": 0.0, "peak_price": 0.0, "entry_date": "N/A"} for h in broker_data}
                pm.set_ledger(new_positions, new_cash)
                print("Ledger updated successfully.")
        else:
            print("Ledger is already reconciled.")

def main():
    logging.basicConfig(level=logging.INFO)
    pm = PortfolioManager()
    
    # Setup CLI
    parser = argparse.ArgumentParser(description="ESMS Control Panel")
    parser.add_argument("--non-interactive", action="store_true", help="Run without user prompts")
    parser.add_argument("--domain", choices=["IN", "US"], default="IN", help="Specify domain (IN/US)")
    subparsers = parser.add_subparsers(dest="command")
    
    # Sync
    subparsers.add_parser("sync", help="Update data")
    
    # Report
    subparsers.add_parser("report", help="Generate action report")
    
    args = parser.parse_args()
    
    # 1. Run Initialization Flow
    initialize_ledger(pm, interactive=not args.non_interactive)
    
    # Instantiate domain-specific orchestrator and engine
    orchestrator = DataOrchestrator(domain=args.domain)
    
    if args.command == "sync":
        orchestrator.sync_universe()
    elif args.command == "report":
        engine = IndicatorEngine(orchestrator)
        
        # Compute scores and export report
        df = engine.compute_alpha_scores(generateReport=True)
        
        if not df.empty:
            # Generate signals and export JSON report
            engine.generate_signals(df, generateReport=True)
            print("\nReport generation complete.")
        else:
            print("No data available to generate report.")

if __name__ == "__main__":
    main()
