# Elite Strategy Management System (ESMS)
## Bridging Backtest to Live Execution

### 1. Core Objectives
The **ESMS** is a domain-agnostic decision support system designed to transition quantitative backtesting into a daily operational tool. It automates the "grunt work" of data ingestion, indicator calculation, and state preservation to maintain a high-performance basket of momentum stocks. While the **Core Engine** remains constant, the system utilizes **Strategy Profiles** to adapt to the specific dynamics of different markets (e.g., India vs. USA).

---

### 2. The Universal Algorithm Briefing
The system operates on a **Relative Strength Momentum** framework consisting of four pillars:

**A. Scoring (Multi-Timeframe RSI)**
Stocks are ranked using a weighted composite of RSI values across Daily, Weekly, and Monthly timeframes. This identifies assets with long-term structural strength and short-term momentum. The specific weighting and "Elite" thresholds vary by market profile.

**B. Dynamic Exposure (Elite Scaling)**
The portfolio's "risk-on" posture is determined by **Opportunity Density**. The system calculates the **Elite Count** (symbols exceeding the threshold).
*   In low-opportunity environments, the basket contracts to **5 slots**.
*   In high-opportunity environments, the basket expands up to **15 slots**.

**C. The Elite Swap Engine**
This is a **Competitive Survival** model. If a new candidate appears with an Alpha Score significantly higher (the **Swap Hurdle**) than the weakest current holding, the system triggers an upgrade to maintain maximum portfolio strength.

**D. The Triple-Guard Exit**
A defensive protocol designed to harvest gains and prune laggards:
1.  **Trend Persistence:** EMA-based price action filters.
2.  **Profit Protection:** A trailing stop (typically 25%) based on the **Peak Price** since entry.
3.  **Context Preservation:** RSI floors to detect structural trend breakdowns.

---

### 3. Strategy Profiles

| Parameter | India (IN) Profile | USA (US) Profile |
| :--- | :--- | :--- |
| **RSI Weighting** | 50% Monthly / 30% Weekly / 20% Daily | 40% Monthly / 40% Weekly / 20% Daily |
| **Elite Threshold** | 130 | 88 |
| **Swap Hurdle** | 20 Points | 20 Points |
| **Trailing Stop** | 25% from Peak | 25% from Peak |

---

### 4. Functional Requirements

#### 4.1 Data Management (DM)
- **DM-1:** Fetch daily OHLCV data post-market (EOD) or pre-open to ensure indicators (RSI, Vol Surge) are calculated on finalized candles.
- **DM-2:** Incrementally update OHLCV data for the entire stock universe (~200 symbols) daily to maintain history for multi-timeframe indicators and 'Elite Count' calculation.
- **DM-3:** Validate data integrity for all downloaded symbols to ensure no missing candles or invalid price points before calculation.
- **DM-4:** Provide a standalone script to display "Elite Stocks" with their component scores for rapid daily scanning.
- **DM-5:** Maintain Benchmark Index data (e.g., NIFTY/S&P500) and calculate market breadth metrics to determine the optimal `max_slots` for the current regime.
- **DM-6:** Verify that data is not missing recent dates (ensuring at least the most recent X trading days are present) before proceeding with scoring.
- **DM-7:** Support multiple data providers (Default: Yahoo Finance) with automated fallback logic if the primary source fails.
- **DM-8:** Implement a notification system to alert the user immediately if data gaps or provider errors are detected.

#### 4.2 Indicator Engine (IE)
- **IE-1:** Calculate 9 and 10-period Exponential Moving Averages (EMA) on daily closing prices.
- **IE-2:** Compute 14-period RSI on Daily, Weekly, and Monthly timeframes to support multi-timeframe analysis.
- **IE-3:** Calculate 20-period Moving Average of Volume to detect relative volume surges.
- **IE-4:** Compute the composite "Alpha Score" using domain-specific RSI weighting (e.g., IN: 50/30/20) plus Volume-based bonuses (e.g., +25 points for Vol Surge > 1.5).
- **IE-5:** [India Only] Flag the "Rocket Signal" (RSI > 40 & Vol > 2.0) and add a +30 point bonus to the total cumulative Alpha Score.
- **IE-6:** Default to computing scores for the entire universe, while providing the capability to process a targeted list of stocks provided as input with detailed calculation logging.

#### 4.3 Portfolio Tracking (PT)
- **PT-1:** Maintain a persistent ledger of active positions (Entry Date, Price, Qty) with capability to cross-check and reconcile against manual user input or real-time broker data.
- **PT-2:** Track and persist the "Peak Price" (Highest High since entry) for every stock currently held in the portfolio.
- **PT-3:** Calculate the current cash balance and total portfolio equity based on real execution prices and latest market values.
- **PT-4:** Build an automated component for broker integration to perform portfolio querying, order placement, and live status management.
- **PT-5:** Develop a background monitoring script that runs continuously to track portfolio health, price alerts, and provide real-time status notifications.

#### 4.4 Exit Logic (EL)
- **EL-1:** Flag a SELL signal if the daily High falls below the 10-period EMA and execute automated exits via broker integration.
- **EL-2:** Flag a SELL signal if the daily Low breaches 25% below the recorded Peak Price (Trailing Stop).
- **EL-3:** Flag a SELL signal if Weekly or Monthly RSI drops below 40 (Context Loss).

#### 4.5 Selection & Swap Engine (SE)
- **SE-1:** Rank all candidate stocks by Alpha Score and filter for active "Signal" status.
- **SE-2:** Dynamically adjust portfolio capacity (5 to 15 slots) based on the "Elite Count"; implement a "Defensive Mode" that forces capacity to minimum (5 slots) and halts new entries if the Benchmark Index is below its 200-day EMA.
- **SE-3:** Identify the weakest holding (lowest Alpha Score) to evaluate for potential swap opportunities.
- **SE-4:** Suggest a SWAP only if a candidate's Alpha Score exceeds the weakest holding's score by > 20 points.

#### 4.6 User Interface & Execution (UI)
- **UI-1:** Provide a command-line interface to generate the daily "Action Report" showing all Buy, Sell, and Swap recommendations.
- **UI-2:** Implement manual commands to record trade executions (Buy/Sell) and update the persistent ledger.
- **UI-3:** Display a portfolio status dashboard showing current PnL, exposure levels, and market strength metrics.

---

### 5. Operational Stability & Developer Sanity (OSDS)
- **OSDS-1:** Implement detailed logging across all modules (Data, Engine, Portfolio, Broker) to record every decision, signal, and execution for auditability.

---

### 6. Operational Workflow

| Phase | Time | Action |
| :--- | :--- | :--- |
| **Sync** | Post-Market / Pre-Open | Fetch latest EOD data and update indicators via Data Manager. |
| **Analyze** | Pre-Market | Generate the Action Report (Sells, Swaps, Buys) via Engine. |
| **Execute** | Market Hours | Automated exits/entries via PT-4 and manual broker confirmation. |
| **Monitor** | Market Hours | Background service (PT-5) tracks health and stop-loss hits. |
| **Log** | Post-Execution | ESMS updates persistent ledger and detailed logs. |

---

### 7. Technical Components (Proposed)

#### 7.1 Data Manager (`orchestrator.py`)
- **Concept:** The Librarian. Single source of truth for historical and benchmark market data.
- **Interfaces:**
    - `sync_universe()` -> **Output:** `bool` (Success status).
    - `getOHLCVFromDataStore(symbol: str)` -> **Output:** `pd.DataFrame` (Validated OHLCV data).
    - `get_index_status()` -> **Output:** `dict` (Keys: `symbol`, `price`, `ema_200`, `is_bullish`).
- **Procedure (Execution Logic):**
    1. **Inventory Check:** Scans the `data/` folder and identifies the `max(Date)` in each CSV.
    2. **Incremental Fetch:** Calls primary provider (Yahoo Finance) to get data from `last_date + 1` to `today`.
    3. **Fallback Logic:** If the primary source fails, automatically attempts retrieval from secondary providers.
    4. **Validation:** Checks for missing recent dates or invalid price points (e.g., zero volume on trading days).
    5. **Commit:** Appends new rows to CSVs and updates the 200-EMA for the Benchmark Index.

#### 7.2 Indicator Engine (`engine.py`)
- **Concept:** The Brain. Quantitative processor for Alpha King scoring and regime analysis.
- **Interfaces:**
    - `compute_alpha_scores(symbols: list[str] = None)` -> **Output:** `pd.DataFrame` (Ranked stocks with multi-timeframe RSI and Alpha scores).
    - `generate_signals(df_scored: pd.DataFrame)` -> **Output:** `dict` (Lists of symbols for `Rocket`, `Entry`, and `Swap` candidates).
    - `assess_market_regime(df_scored: pd.DataFrame)` -> **Output:** `dict` (Keys: `elite_count`, `max_slots`, `defensive_mode`).
- **Procedure (Execution Logic):**
    1. **Data Preparation:** Loads OHLCV and resamples Daily data to Weekly and Monthly timeframes **for each symbol**.
    2. **Indicator Calculation:** Computes 14-period RSI (D/W/M), EMAs (9/10), and 20-period Volume MA **per symbol**.
    3. **Scoring Engine:** Applies the Strategy Profile weighting (e.g., 50/30/20) plus Volume and Rocket bonuses **to each symbol individually**.
    4. **Regime Check:** Determines `max_slots` (5–15) and sets "Defensive Mode" based on Index 200-EMA.
    5. **Logging:** Records every intermediate value and decision point for auditability.

#### 7.3 Portfolio Manager (`portfolio_manager.py`)
- **Concept:** The Accountant. State preservation and trailing-stop management.
- **Interfaces:**
    - `update_peak(symbol: str, high: float)` -> **Output:** `bool` (True if new peak stored).
    - `reconcile_with_broker(broker_holdings: list[dict])` -> **Output:** `list[str]` (Discrepancy logs).
    - `get_active_positions()` -> **Output:** `dict[str, dict]` (Symbol to entry/peak/qty mapping).
- **Procedure (Execution Logic):**
    1. **Execution Mode:** Can run **Synchronously** (immediate status update) or **Asynchronously** (daily background update to ensure GTT orders are modified to follow trailing stops).
    2. **Peak Monitoring:** Compares latest High with stored Peak for each held symbol; updates if a new high is reached.
    3. **Trigger Scan:** Evaluates positions against the "Triple Guard" (EMA10, 25% Stop, RSI context).
    4. **Reconciliation:** Cross-checks ledger against broker data for quantity or position mismatches.
    5. **Persistence:** Atomically saves the updated state to `portfolio.json`.

#### 7.4 Broker Connector (`broker_connector.py`)
- **Concept:** The Executor (Optional/Long-term). Abstraction layer for automated broker API communication.
- **Functionality:** Provides automated order execution (Buy/Sell) as a long-term goal; manual execution and confirmation are the primary fallback.
- **Interfaces:**
    - `execute_order(symbol: str, action: str, qty: int)` -> **Output:** `dict` (Fill details: `id`, `price`, `status`).
    - `fetch_holdings()` -> **Output:** `list[dict]` (Active broker-side positions).
    - `get_margin()` -> **Output:** `float` (Available trading cash).
- **Procedure (Execution Logic):**
    1. **Automated Mode (Optional):** Establish secure session -> Map symbols -> Dispatch orders -> Confirm fills.
    2. **Manual Mode (Default):** System provides action instructions; user executes in broker terminal and confirms in ESMS.

#### 7.5 Monitor Service (`monitor_service.py`)
- **Concept:** The Watchdog. A background script that stays awake while you work.
- **Interfaces:**
    - `heartbeat()` -> **Output:** `datetime` (Last loop timestamp).
    - `notify(message: str)` -> **Output:** `bool` (Success status).
    - `start_monitoring()` -> **Output:** `None`.
- **Procedure (Execution Logic):**
    1. **Polling Loop:** Fetches the latest price of held stocks every 5–15 minutes during market hours.
    2. **Stop Trigger:** If a stock breaches its 25% Trailing Stop intraday, it triggers the Broker Connector for immediate exit.
    3. **Alerting:** Sends immediate notifications: *"Warning: RELIANCE has breached 25% Trailing Stop. Automated exit initiated."*

#### 7.6 CLI Manager (`cli_manager.py`)
- **Concept:** The Control Panel. User interaction and system orchestration hub.
- **Interfaces:**
    - `cmd_sync()` -> **Output:** `None`.
    - `cmd_report()` -> **Output:** `None`.
    - `cmd_status()` -> **Output:** `None`.
- **Procedure (Execution Logic):**
    1. **Command Routing:** Maps user CLI input to the appropriate component workflows.
    2. **Orchestration:** Coordinates the sequence (Sync -> Reconcile -> Analyze -> Report).
    3. **Presentation:** Formats raw data into readable tables, dashboards, and Elite stock reports.
