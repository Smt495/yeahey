"""Assess likely market impact of aggregated news and macro data."""
from __future__ import annotations
from briefing.config import WATCH_STOCKS, SECTOR_KEYWORDS, STOCK_KEYWORDS


def _impact_level(score: int) -> str:
    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def classify_articles(articles: list[dict]) -> dict[str, list[dict]]:
    """
    Returns a dict keyed by stock symbol / sector with the most relevant
    bullish and bearish articles, each tagged with an impact level.
    """
    classified: dict[str, dict[str, list]] = {
        sym: {"bullish": [], "bearish": [], "neutral": []}
        for sym in list(WATCH_STOCKS.keys()) + ["Aviation", "AI", "Macro"]
    }

    for art in articles:
        scores   = art.get("scores", {})
        sentiment = art.get("sentiment", "neutral")
        tagged = {**art, "impact": _impact_level(sum(scores.values()))}

        for category, _score in scores.items():
            if category in classified:
                classified[category][sentiment].append(tagged)

    # Deduplicate (same article can match multiple tickers)
    for cat in classified:
        for bucket in ("bullish", "bearish", "neutral"):
            seen: set[str] = set()
            deduped = []
            for a in classified[cat][bucket]:
                key = a["title"].lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(a)
            classified[cat][bucket] = deduped[:10]

    return classified


def summarize_market_impact(quotes: dict, classified_news: dict) -> dict:
    """
    Build a high-level daily narrative for each watched stock:
    overall bias, top catalysts, risk flags.
    """
    summaries = {}
    for sym, name in WATCH_STOCKS.items():
        q    = quotes.get(sym, {})
        news = classified_news.get(sym, {})

        bull_count = len(news.get("bullish", []))
        bear_count = len(news.get("bearish", []))
        chg        = q.get("change_pct")
        vol_ratio  = q.get("vol_ratio")

        if bull_count > bear_count:
            bias = "Bullish"
        elif bear_count > bull_count:
            bias = "Bearish"
        else:
            bias = "Neutral"

        flags = []
        if vol_ratio and vol_ratio > 2.0:
            flags.append(f"Volume {vol_ratio:.1f}x avg — unusual activity")
        if chg and chg <= -5:
            flags.append(f"Price down {chg:.1f}% — significant decline")
        elif chg and chg >= 5:
            flags.append(f"Price up {chg:.1f}% — strong move")
        high_impact_bull = [a for a in news.get("bullish", []) if a.get("impact") == "HIGH"]
        high_impact_bear = [a for a in news.get("bearish", []) if a.get("impact") == "HIGH"]
        if high_impact_bear:
            flags.append(f"{len(high_impact_bear)} HIGH-impact bearish headline(s)")
        if high_impact_bull:
            flags.append(f"{len(high_impact_bull)} HIGH-impact bullish headline(s)")

        summaries[sym] = {
            "name":       name,
            "bias":       bias,
            "flags":      flags,
            "bull_count": bull_count,
            "bear_count": bear_count,
        }
    return summaries
