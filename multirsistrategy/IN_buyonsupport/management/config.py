import os

# Base Directory is now the 'management' folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Operational Paths relative to 'management'
DATA_DIR = os.path.join(BASE_DIR, 'data_live')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
STATE_DIR = os.path.join(BASE_DIR, 'state')

# Ensure directories exist
os.makedirs(os.path.join(DATA_DIR, 'IN'), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'US'), exist_ok=True)
# ...
def get_domain_data_dir(domain):
    return os.path.join(DATA_DIR, domain)

# Portfolio State
STATE_FILE = os.path.join(STATE_DIR, 'portfolio_state.json')

# Strategy Profiles
STRATEGY_PROFILES = {
    "IN": {
        "benchmark": "^NSEI",  # Nifty 50
        "rsi_weights": {"monthly": 0.5, "weekly": 0.3, "daily": 0.2},
        "elite_thresh": 130,
        "swap_hurdle": 20,
        "trailing_stop": 0.25,
        "rocket_enabled": True
    },
    "US": {
        "benchmark": "^GSPC",  # S&P 500
        "rsi_weights": {"monthly": 0.4, "weekly": 0.4, "daily": 0.2},
        "elite_thresh": 88,
        "swap_hurdle": 20,
        "trailing_stop": 0.25,
        "rocket_enabled": False
    }
}

# Current Active Profile
ACTIVE_PROFILE = "IN"

# Data Provider Configuration
PRIMARY_PROVIDER = "yahoo"
FALLBACK_PROVIDERS = [] 
RECENT_DAYS_REQUIRED = 5 

# Tickers
TICKERS_IN = [
    "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENSOL", 
    "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ALKEM", "AMBUJACEM", 
    "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "ATUL", 
    "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", 
    "BAJAJHLDNG", "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BANKINDIA", 
    "BATAINDIA", "BEL", "BERGEPAINT", "BHARTIARTL", "BHEL", "BIOCON", "BOSCHLTD", 
    "BPCL", "BRITANNIA", "BSOFT", "CANBK", "CANFINHOME", "CHAMBLFERT", "CHOLAFIN", 
    "CIPLA", "COALINDIA", "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "CROMPTON", 
    "CUMMINSIND", "DABUR", "DALBHARAT", "DEEPAKNTR", "DELHIVERY", "DIVISLAB", 
    "DIXON", "DLF", "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", "FEDERALBNK", 
    "GAIL", "GLENMARK", "GMRINFRA", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES", 
    "GRASIM", "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", 
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", 
    "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDFCFIRSTB", "IEX", "IGL", 
    "INDHOTEL", "INDIACEM", "INDIAMART", "INDIANB", "INDIGO", "INDUSINDBK", 
    "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRFC", "IRCTC", "ITC", "JINDALSTEL", 
    "JIOFIN", "JKCEMENT", "JSWENERGY", "JSWSTEEL", "JUBLFOOD", "KOTAKBANK", 
    "LALPATHLAB", "LICHSGFIN", "LICI", "LT", "LTIM", "LTTS", "LUPIN", 
    "M&M", "M&MFIN", "MANAPPURAM", "MARICO", "MARUTI", "MCX", "METROPOLIS", 
    "MFSL", "MGL", "MOTHERSON", "MPHASIS", "MRF", "MUTHOOTFIN", "NATIONALUM", 
    "NAUKRI", "NAVINFLUOR", "NESTLEIND", "NHPC", "NMDC", "NTPC", "OBEROIRLTY", 
    "OFSS", "ONGC", "PAGEIND", "PERSISTENT", "PETRONET", "PFC", 
    "PIDILITIND", "PIIND", "PNB", "POLYCAB", "POWERGRID", "PVRINOX", "RAMCOCEM", 
    "RBLBANK", "RECLTD", "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN", 
    "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SRF", "SUNPHARMA", "SUNTV", "SYNGENE", 
    "TATACOMM", "TATACONSUM", "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL", 
    "TCS", "TECHM", "TITAN", "TORNTPHARM", "TRENT", "TVSMOTOR", "UBL", 
    "ULTRACEMCO", "UPL", "VEDL", "VOLTAS", "WIPRO", "ZEEL", "ZYDUSLIFE"
]

TICKERS_US = [
    "AAPL", "ABBV", "ABNB", "ABT", "ACN", "ADBE", "ADI", "ADM", "ADP", "ADSK", "AEP", "AIG", "ALL", "AMAT", "AMD", 
    "AMGN", "AMT", "AMZN", "ARM", "ASML", "AVGO", "AXP", "BA", "BAC", "BEN", "BK", "BKNG", "BKR", "BLK", "BMY", 
    "BRK-B", "BSX", "C", "CAT", "CB", "CDNS", "CHTR", "CI", "CL", "CMCSA", "COF", "COIN", "COP", "COST", "CPRT", 
    "CRM", "CRWD", "CSCO", "CTAS", "CVS", "CVX", "DE", "DHR", "DIS", "DOW", "DUK", "EL", "EMR", "EQIX", "EXC", 
    "F", "FAST", "FDX", "FIS", "FTNT", "GD", "GE", "GEHC", "GILD", "GM", "GOOG", "GOOGL", "GS", "HD", "HON", "HOOD", 
    "IBM", "INTC", "INTU", "ISRG", "JD", "JNJ", "JPM", "KDP", "KHC", "KLAC", "KMI", "KO", "LIN", "LLY", "LMT", "LOW", 
    "LRCX", "MA", "MAR", "MARA", "MCD", "MCHP", "MDLZ", "MDT", "MELI", "MET", "META", "MMM", "MO", "MRK", "MS", 
    "MSFT", "MSTR", "MU", "NEE", "NET", "NFLX", "NKE", "NOW", "NVDA", "NXPI", "ORCL", "ORLY", "OXY", "PANW", "PDD", 
    "PEP", "PFE", "PG", "PLD", "PLTR", "PM", "PYPL", "QCOM", "QQQ", "REGN", "RIOT", "ROKU", "ROST", "RTX", "SBUX", 
    "SCCO", "SCHW", "SE", "SHOP", "SLB", "SMCI", "SNOW", "SNPS", "SO", "SOFI", "SPG", "SPY", "SYK", "T", "TGT", 
    "TJX", "TMO", "TMUS", "TSLA", "TXN", "U", "UNH", "UNP", "UPS", "USB", "V", "VRTX", "VZ", "WBD", "WFC", "WMT", 
    "XOM", "ZM", "ZTS"
]

def get_current_tickers():
    return TICKERS_IN if ACTIVE_PROFILE == "IN" else TICKERS_US

def get_profile():
    return STRATEGY_PROFILES[ACTIVE_PROFILE]
