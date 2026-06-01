"""Central configuration for the US Stock Daily Briefing system."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Tracked universe ──────────────────────────────────────────────────────────
WATCH_STOCKS = {
    "RKLB": "Rocket Lab USA",
    "NOK":  "Nokia Corporation",
    "CPSH": "CPS Technologies",
}

SECTOR_ETFS = {
    "AI": {
        "BOTZ":  "Global X Robotics & AI ETF",
        "AIQ":   "Global X AI & Technology ETF",
        "ARKQ":  "ARK Autonomous Tech & Robotics ETF",
        "SMH":   "VanEck Semiconductor ETF",
    },
    "Space": {
        "ARKX":  "ARK Space Exploration ETF",
        "UFO":   "Procure Space ETF",
    },
    "Storage": {
        "MU":    "Micron Technology",
        "WDC":   "Western Digital",
        "STX":   "Seagate Technology",
    },
}

MARKET_INDICES = {
    "^GSPC":  "S&P 500",
    "^IXIC":  "NASDAQ Composite",
    "^DJI":   "Dow Jones",
    "^RUT":   "Russell 2000",
    "^VIX":   "VIX Fear Index",
    "QQQ":    "Invesco QQQ (NASDAQ-100)",
    "SPY":    "SPDR S&P 500 ETF",
    "GLD":    "SPDR Gold Trust",
    "TLT":    "iShares 20+ Year Treasury Bond ETF",
    "DX-Y.NYB": "US Dollar Index",
    "CL=F":   "Crude Oil WTI Futures",
}

AVIATION_PEERS = []
AI_PEERS       = ["NVDA", "MSFT", "GOOGL", "META", "AMD", "INTC", "TSM", "AVGO"]
SPACE_PEERS    = ["RKLB", "SPCE", "LMT", "RTX", "NOC", "HII", "KTOS", "ASTS"]
STORAGE_PEERS  = ["MU", "WDC", "STX", "NAND", "NVME"]  # MU/WDC/STX are real tickers

# Broader scan universe for "Strong Stock of the Day"
STRONG_STOCK_UNIVERSE = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","TSLA","AMD","AVGO","TSM",
    "JPM","GS","BAC","WFC","MS","BLK",
    "DAL","UAL","BA","LMT","RTX","NOC",
    "RKLB","ASTS","KTOS","SPCE",
    "MU","WDC","STX","AMAT","KLAC","LRCX",
    "XOM","CVX","SLB","OXY",
    "UNH","LLY","JNJ","PFE","MRNA",
    "NOK","ERIC","QCOM","ANET","CSCO",
    "CPSH","MSTR","PLTR","IONQ","QUBT",
]

# ── News RSS feeds ─────────────────────────────────────────────────────────────
NEWS_FEEDS = [
    # Major financial news
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=RKLB,NOK,CPSH&region=US&lang=en-US",
    "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://finance.yahoo.com/news/rssindex",
    # Space / Defense
    "https://spacenews.com/feed/",
    "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
    # Tech / AI
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    # Economic indicators
    "https://www.federalreserve.gov/feeds/press_all.xml",
]

# ── Sector-specific search keywords ───────────────────────────────────────────
SECTOR_KEYWORDS = {
    "AI": [
        "artificial intelligence", "AI", "machine learning", "LLM", "GPU",
        "semiconductor", "data center", "NVIDIA", "OpenAI", "Anthropic",
        "generative AI", "inference", "neural network", "foundation model",
        "transformer", "compute", "AI chip", "training run",
    ],
    "Space": [
        "space launch", "rocket", "satellite", "orbit", "SpaceX", "Rocket Lab",
        "commercial space", "launch vehicle", "reusable rocket", "LEO", "GEO",
        "space station", "NASA", "DARPA", "NRO", "space force", "Starlink",
        "neutron", "electron", "Falcon", "constellation",
    ],
    "Storage": [
        "NAND flash", "DRAM", "memory chip", "storage", "SSD", "HDD",
        "Micron", "Western Digital", "Seagate", "hard drive", "data storage",
        "memory pricing", "oversupply", "inventory correction", "HBM",
        "high bandwidth memory", "flash memory",
    ],
    "Macro": [
        "Federal Reserve", "Fed rate", "CPI", "inflation", "GDP", "unemployment",
        "tariff", "trade war", "recession", "earnings", "interest rate",
        "Treasury yield", "FOMC", "jobs report", "nonfarm payroll",
        "Jerome Powell", "rate cut", "rate hike", "quantitative tightening",
    ],
}

# Individual stock keywords for news relevance scoring
STOCK_KEYWORDS = {
    "RKLB": ["Rocket Lab", "RKLB", "neutron", "electron rocket", "space launch",
             "SPAC", "small satellite", "launch vehicle"],
    "NOK":  ["Nokia", "NOK", "5G network", "telecom equipment", "Ericsson",
             "network infrastructure", "patent", "mobile broadband"],
    "CPSH": ["CPS Technologies", "CPSH", "metal matrix composite", "MMC",
             "power electronics", "ceramic", "defense electronics",
             "thermal management"],
}

# ── Scheduling (Eastern Time) ──────────────────────────────────────────────────
SCHEDULE_TIMES = {
    "pre_market":   "07:30",   # Pre-market briefing
    "market_open":  "09:35",   # Open snapshot
    "midday":       "12:00",   # Midday update
    "close":        "16:05",   # After-hours / close summary
    "after_hours":  "17:30",   # After-hours movers
}

# ── Report output ──────────────────────────────────────────────────────────────
REPORTS_DIR   = os.path.join(os.path.dirname(__file__), "..", "reports")
TIMEZONE      = "America/New_York"
MAX_NEWS_AGE_HOURS = 24
MAX_NEWS_PER_SOURCE = 10
