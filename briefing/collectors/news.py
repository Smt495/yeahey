"""News aggregator: RSS feeds + Yahoo Finance news + keyword scoring."""
import feedparser
import requests
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from briefing.config import (
    NEWS_FEEDS, SECTOR_KEYWORDS, STOCK_KEYWORDS,
    WATCH_STOCKS, MAX_NEWS_AGE_HOURS, MAX_NEWS_PER_SOURCE,
)

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _parse_date(entry) -> datetime | None:
    for field in ("published", "updated", "created"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _score_article(title: str, summary: str) -> dict:
    """Return relevance scores per category and a combined sentiment hint."""
    text = (title + " " + summary).lower()
    scores = {}
    for category, keywords in {**SECTOR_KEYWORDS, **STOCK_KEYWORDS}.items():
        hit = sum(1 for kw in keywords if kw.lower() in text)
        if hit:
            scores[category] = hit

    # Naive sentiment: count bullish / bearish signal words
    bullish_words = [
        "surge", "jump", "soar", "beat", "record", "upgrade", "buy",
        "growth", "profit", "strong", "partnership", "contract", "win",
        "gain", "rally", "breakthrough", "approval", "launch",
    ]
    bearish_words = [
        "fall", "drop", "plunge", "miss", "downgrade", "sell", "loss",
        "delay", "cancel", "fine", "lawsuit", "decline", "crash", "layoff",
        "cut", "risk", "warning", "concern", "probe", "investigation",
    ]
    bull_hits = sum(1 for w in bullish_words if w in text)
    bear_hits = sum(1 for w in bearish_words if w in text)
    if bull_hits > bear_hits:
        sentiment = "bullish"
    elif bear_hits > bull_hits:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {"scores": scores, "sentiment": sentiment}


def _fetch_rss(url: str, cutoff: datetime) -> list[dict]:
    articles = []
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
        for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:
            pub = _parse_date(entry)
            if pub and pub < cutoff:
                continue
            title   = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            link    = getattr(entry, "link", "")
            scored  = _score_article(title, summary)
            if not scored["scores"]:
                continue       # irrelevant to our universe
            articles.append({
                "title":     title,
                "summary":   summary[:300],
                "url":       link,
                "source":    feed.feed.get("title", url),
                "published": pub,
                **scored,
            })
    except Exception as e:
        log.debug("RSS fetch failed %s: %s", url, e)
    return articles


def _fetch_yf_stock_news(symbols: list[str], cutoff: datetime) -> list[dict]:
    """Pull news directly from Yahoo Finance ticker objects."""
    import yfinance as yf
    articles = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            for item in (t.news or []):
                pub_ts = item.get("providerPublishTime")
                if pub_ts:
                    pub = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                    if pub < cutoff:
                        continue
                else:
                    pub = None
                content = item.get("content") or {}
                title   = content.get("title") or item.get("title", "")
                summary = content.get("summary") or item.get("summary", "")
                url     = (
                    (content.get("canonicalUrl") or {}).get("url")
                    or item.get("link", "")
                )
                scored = _score_article(title, summary)
                scored["scores"].setdefault(sym, 1)    # always relevant to this ticker
                articles.append({
                    "title":     title,
                    "summary":   summary[:300],
                    "url":       url,
                    "source":    f"Yahoo Finance ({sym})",
                    "published": pub,
                    **scored,
                })
        except Exception as e:
            log.debug("YF news(%s): %s", sym, e)
    return articles


def fetch_all_news() -> list[dict]:
    """Aggregate all news, deduplicate by title, sort by date desc."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_NEWS_AGE_HOURS)
    articles: list[dict] = []

    # RSS feeds
    for url in NEWS_FEEDS:
        articles.extend(_fetch_rss(url, cutoff))

    # Yahoo Finance per-ticker news
    all_symbols = (
        list(WATCH_STOCKS.keys())
        + ["JETS", "SMH", "BOTZ", "AIQ", "ARKQ"]
        + ["DAL", "UAL", "NVDA", "MSFT", "BA"]
    )
    articles.extend(_fetch_yf_stock_news(all_symbols, cutoff))

    # Deduplicate by lower-cased title
    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        key = a["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique.sort(key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return unique
