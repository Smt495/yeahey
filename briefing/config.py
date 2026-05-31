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
    "Aviation": {
        "JETS":  "US Global Jets ETF",
        "XAL":   "AMEX Airline Index (legacy ref)",
    },
    "AI": {
        "BOTZ":  "Global X Robotics & AI ETF",
        "AIQ":   "Global X AI & Technology ETF",
        "ARKQ":  "ARK Autonomous Tech & Robotics ETF",
        "SOXS":  "Direxion Semi Bear 3x (ref)",
        "SMH":   "VanEck Semiconductor ETF",
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

AVIATION_PEERS = ["DAL", "UAL", "AAL", "LUV", "BA", "AIR.PA", "SAVE", "JBLU"]
AI_PEERS       = ["NVDA", "MSFT", "GOOGL", "META", "AMD", "INTC", "TSM", "AVGO"]

# ── News RSS feeds ─────────────────────────────────────────────────────────────
NEWS_FEEDS = [
    # Major financial news
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=RKLB,NOK,CPSH&region=US&lang=en-US",
    "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://finance.yahoo.com/news/rssindex",
    # Aerospace / Aviation
    "https://www.aviationweek.com/rss",
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
    "Aviation": [
        "airline", "aviation", "aerospace", "commercial aviation", "air travel",
        "jet fuel", "FAA", "IATA", "aircraft", "Boeing", "Airbus", "airport",
        "passenger traffic", "load factor",
    ],
    "AI": [
        "artificial intelligence", "AI", "machine learning", "LLM", "GPU",
        "semiconductor", "data center", "NVIDIA", "OpenAI", "Anthropic",
        "generative AI", "inference", "neural network",
    ],
    "Macro": [
        "Federal Reserve", "Fed rate", "CPI", "inflation", "GDP", "unemployment",
        "tariff", "trade war", "recession", "earnings", "interest rate",
        "Treasury yield", "FOMC", "jobs report", "nonfarm payroll",
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
