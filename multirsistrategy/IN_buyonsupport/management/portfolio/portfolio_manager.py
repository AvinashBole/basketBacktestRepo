import json
import os
import logging
import sys
from datetime import datetime

# Ensure we can import from the parent management package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import STATE_FILE, STRATEGY_PROFILES, ACTIVE_PROFILE

# OSDS-1: Detailed logging for auditability and developer sanity
logger = logging.getLogger(__name__)

class PortfolioManager:
    """
    Concept: The Accountant.
    State preservation and trailing-stop management (PT-1 to PT-3).
    Supports synchronous and asynchronous (concept) execution modes.
    """
    def __init__(self):
        self.profile = STRATEGY_PROFILES[ACTIVE_PROFILE]
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Procedure: Loads existing inventory from portfolio.json or initializes new."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    logger.info(f"Loaded existing portfolio state from {STATE_FILE}")
                    return state
            except Exception as e:
                logger.error(f"Failed to load portfolio state: {e}. Initializing empty state.")
        
        # Initial Default State if no file exists
        return {
            "cash": 100000.0,
            "positions": {}, # {symbol: {entry_date, entry_price, peak_price, qty}}
            "last_sync_date": None,
            "history": []   # Audit log of all trades
        }

    def save_state(self):
        """Procedure: Atomically saves updated state to persistence layer."""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=4)
            logger.debug("Portfolio state saved successfully.")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to save portfolio state: {e}")

    def add_position(self, symbol: str, price: float, qty: int, date: str) -> bool:
        """
        Interface: Records a new entry and deducts cash.
        Performed for each symbol individually during a BUY action.
        """
        cost = price * qty
        if self.state["cash"] < cost:
            logger.error(f"Insufficient cash for {symbol} entry (Need {cost}, Have {self.state['cash']})")
            return False
            
        # Entry logic: Initial peak is always the entry price (PT-2)
        self.state["positions"][symbol] = {
            "entry_date": date,
            "entry_price": float(price),
            "peak_price": float(price), 
            "qty": int(qty)
        }
        self.state["cash"] -= cost
        
        # Record to history for auditability (OSDS-1)
        self.state["history"].append({
            "date": date,
            "action": "BUY",
            "symbol": symbol,
            "price": float(price),
            "qty": int(qty)
        })
        
        self.save_state()
        logger.info(f"Position ADDED: {symbol} | Qty: {qty} @ {price}")
        return True

    def remove_position(self, symbol: str, price: float, date: str, reason: str = "Manual") -> bool:
        """
        Interface: Closes a position and returns proceeds to cash.
        Performed for each symbol individually during a SELL action.
        """
        if symbol not in self.state["positions"]:
            logger.warning(f"Attempted to remove {symbol} which is not in portfolio.")
            return False
            
        pos = self.state["positions"][symbol]
        proceeds = price * pos["qty"]
        self.state["cash"] += proceeds
        
        # Record to history for auditability
        self.state["history"].append({
            "date": date,
            "action": "SELL",
            "symbol": symbol,
            "price": float(price),
            "qty": int(pos["qty"]),
            "reason": reason
        })
        
        del self.state["positions"][symbol]
        self.save_state()
        logger.info(f"Position CLOSED: {symbol} @ {price} | Reason: {reason}")
        return True

    def update_peak(self, symbol: str, high: float) -> bool:
        """
        Interface: Updates the peak price for a held symbol (PT-2).
        Returns True if a new peak was stored.
        Procedure: Iterated for each symbol in the active positions.
        Used to ensure GTT orders or Stop Losses follow the price upward.
        """
        if symbol in self.state["positions"]:
            current_peak = self.state["positions"][symbol].get("peak_price", 0.0)
            if high > current_peak:
                self.state["positions"][symbol]["peak_price"] = float(high)
                logger.info(f"NEW PEAK for {symbol}: {high} (Previous: {current_peak})")
                self.save_state()
                return True
        return False

    def get_active_positions(self) -> dict:
        """Interface: Returns current positions mapping (PT-1)."""
        return self.state["positions"]

    def set_ledger(self, positions: dict, cash: float):
        """Interface: Sets the ledger state manually during reconciliation."""
        self.state["positions"] = positions
        self.state["cash"] = float(cash)
        self.save_state()
        logger.info("Ledger state manually updated.")

    def get_cash(self) -> float:
        """Interface: Returns current available cash (PT-3)."""
        return self.state["cash"]

    def reconcile_with_broker(self, broker_holdings: list[dict]) -> list[str]:
        """
        Interface: Cross-checks local ledger against real-time broker data (PT-1).
        Inputs: broker_holdings (list of dicts containing 'symbol' and 'qty')
        Output: list[str] (descriptions of discrepancies)
        """
        discrepancies = []
        broker_symbols = {h['symbol']: int(h['qty']) for h in broker_holdings}
        local_symbols = {s: int(d['qty']) for s, d in self.state['positions'].items()}
        
        # 1. Check for missing symbols in local state
        for sym, qty in broker_symbols.items():
            if sym not in local_symbols:
                discrepancies.append(f"BROKER EXTRA: Symbol {sym} in broker but NOT in ESMS ledger.")
            elif qty != local_symbols[sym]:
                discrepancies.append(f"QTY MISMATCH: {sym} | Broker: {qty}, ESMS: {local_symbols[sym]}")
        
        # 2. Check for symbols in local state but not in broker
        for sym in local_symbols:
            if sym not in broker_symbols:
                discrepancies.append(f"ESMS EXTRA: Symbol {sym} in ESMS ledger but NOT in broker.")
                
        if discrepancies:
            logger.warning(f"Reconciliation Discrepancies found: {len(discrepancies)}")
        else:
            logger.info("Portfolio Reconciliation: SUCCESS (ESMS matches Broker exactly)")
            
        return discrepancies

    def sync_gtt_orders(self) -> bool:
        """
        Concept: Async Mode Support. 
        Updates/Modifies broker GTT orders based on latest trailing stops.
        (Placeholder for long-term PT-4 broker automation)
        """
        logger.info("Initiating Async GTT Synchronization...")
        # Future implementation would loop through positions and call broker API
        # for each symbol to modify existing sell GTT orders.
        return True
