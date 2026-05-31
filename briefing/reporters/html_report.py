"""Render the daily briefing as a self-contained HTML file."""
from __future__ import annotations
import os
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytz

from briefing.config import REPORTS_DIR, TIMEZONE, WATCH_STOCKS, MARKET_INDICES

ET = pytz.timezone(TIMEZONE)
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def _fmt_price(v) -> str:
    if v is None:
        return "—"
    try:
        return f"${float(v):,.4f}" if float(v) < 10 else f"${float(v):,.2f}"
    except Exception:
        return str(v)


def _fmt_pct(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):+.2f}%"
    except Exception:
        return str(v)


def _fmt_vol(v) -> str:
    if v is None:
        return "—"
    try:
        n = int(v)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.0f}K"
        return str(n)
    except Exception:
        return str(v)


def _fmt_mcap(v) -> str:
    if v is None:
        return "—"
    try:
        n = float(v)
        if n >= 1e12:
            return f"${n/1e12:.2f}T"
        if n >= 1e9:
            return f"${n/1e9:.2f}B"
        if n >= 1e6:
            return f"${n/1e6:.2f}M"
        return f"${n:,.0f}"
    except Exception:
        return str(v)


def _pct_color(v) -> str:
    if v is None:
        return "neutral"
    try:
        return "positive" if float(v) >= 0 else "negative"
    except Exception:
        return "neutral"


def _signal_color(sig_type: str) -> str:
    return {"bullish": "positive", "bearish": "negative"}.get(sig_type, "neutral")


def generate_html(
    session: str,
    quotes: dict,
    news_classified: dict,
    technicals: dict,
    impact_summary: dict,
    macro_data: dict,
    options_data: dict,
    earnings: list,
    deep_analysis: dict | None = None,
    trading_advice: list | None = None,
    strong_stocks: list | None = None,
    undervalued_stocks: list | None = None,
) -> str:
    """Render and write HTML report; return the output file path."""
    now = datetime.now(ET)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fname = os.path.join(REPORTS_DIR, f"briefing_{session}_{now.strftime('%Y%m%d_%H%M')}.html")

    # Build template context
    ctx = {
        "session":         session,
        "generated_at":    now.strftime("%A, %B %d %Y  %H:%M ET"),
        "date_str":        now.strftime("%Y-%m-%d"),

        # Market overview cards
        "indices": [
            {
                "symbol": sym,
                "name":   MARKET_INDICES.get(sym, sym),
                "price":  _fmt_price(quotes.get(sym, {}).get("price")),
                "chg":    _fmt_pct(quotes.get(sym, {}).get("change_pct")),
                "color":  _pct_color(quotes.get(sym, {}).get("change_pct")),
            }
            for sym in ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "QQQ",
                        "GLD", "CL=F", "TLT", "DX-Y.NYB"]
        ],

        # Watch stocks (enriched with deep analysis)
        "watch_stocks": [
            {
                "symbol":    sym,
                "name":      WATCH_STOCKS[sym],
                "price":     _fmt_price(quotes.get(sym, {}).get("price")),
                "open":      _fmt_price(quotes.get(sym, {}).get("open")),
                "high":      _fmt_price(quotes.get(sym, {}).get("high")),
                "low":       _fmt_price(quotes.get(sym, {}).get("low")),
                "chg":       _fmt_pct(quotes.get(sym, {}).get("change_pct")),
                "color":     _pct_color(quotes.get(sym, {}).get("change_pct")),
                "volume":    _fmt_vol(quotes.get(sym, {}).get("volume")),
                "avg_vol":   _fmt_vol(quotes.get(sym, {}).get("avg_volume")),
                "vol_ratio": quotes.get(sym, {}).get("vol_ratio"),
                "mcap":      _fmt_mcap(quotes.get(sym, {}).get("market_cap")),
                "pe":        quotes.get(sym, {}).get("pe"),
                "eps":       quotes.get(sym, {}).get("eps"),
                "beta":      quotes.get(sym, {}).get("beta"),
                "w52h":      _fmt_price(quotes.get(sym, {}).get("52w_high")),
                "w52l":      _fmt_price(quotes.get(sym, {}).get("52w_low")),
                "ret5d":     _fmt_pct(quotes.get(sym, {}).get("ret_5d")),
                "tech":      technicals.get(sym, {}),
                "options":   options_data.get(sym),
                # All news for reference links only (shown at bottom of section)
                "all_news":  (
                    news_classified.get(sym, {}).get("bullish", []) +
                    news_classified.get(sym, {}).get("bearish", []) +
                    news_classified.get(sym, {}).get("neutral", [])
                )[:12],
                "impact":    impact_summary.get(sym, {}),
                "deep":      (deep_analysis or {}).get(sym, {}),
            }
            for sym in WATCH_STOCKS
        ],

        # Sector analysis (all 4 sectors)
        "sectors": {
            sector: {
                "label": {
                    "Aviation": "✈ 商业航空",
                    "AI":       "🤖 AI & 半导体",
                    "Space":    "🚀 商业航天",
                    "Storage":  "💾 存储芯片",
                }.get(sector, sector),
                "bull_points": [
                    f"[{a.get('impact','')}] {a['title']} （{a.get('source','')}）"
                    for a in news_classified.get(sector, {}).get("bullish", [])[:8]
                ],
                "bear_points": [
                    f"[{a.get('impact','')}] {a['title']} （{a.get('source','')}）"
                    for a in news_classified.get(sector, {}).get("bearish", [])[:8]
                ],
                "all_news": (
                    news_classified.get(sector, {}).get("bullish", []) +
                    news_classified.get(sector, {}).get("bearish", [])
                )[:12],
            }
            for sector in ["Aviation", "AI", "Space", "Storage"]
        },

        # Macro
        "macro":    macro_data,
        "earnings": earnings,

        # New panels
        "trading_advice":    trading_advice or [],
        "strong_stocks":     strong_stocks or [],
        "undervalued_stocks": undervalued_stocks or [],
    }

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["fmt_price"] = _fmt_price
    env.filters["fmt_pct"]   = _fmt_pct
    env.filters["pct_color"] = _pct_color
    env.filters["sig_color"] = _signal_color
    env.filters["enumerate"] = enumerate

    template = env.get_template("briefing.html.jinja2")
    html     = template.render(**ctx)

    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)

    return fname
