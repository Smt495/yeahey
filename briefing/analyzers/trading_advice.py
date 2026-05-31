"""
Trading advice engine + Strong Stock / Undervalued Stock scanner.
All rule-based — no external LLM dependency.
"""
from __future__ import annotations
import logging
import yfinance as yf
import pandas as pd

from briefing.config import WATCH_STOCKS, STRONG_STOCK_UNIVERSE

log = logging.getLogger(__name__)

# ── Rating helpers ─────────────────────────────────────────────────────────────

def _rating(score: float) -> str:
    if score >= 3.5:   return "强力买入"
    if score >= 2.0:   return "买入"
    if score >= 0.5:   return "持有/观望"
    if score >= -1.0:  return "减持"
    return "卖出"

def _rating_en(score: float) -> str:
    if score >= 3.5:   return "STRONG BUY"
    if score >= 2.0:   return "BUY"
    if score >= 0.5:   return "HOLD"
    if score >= -1.0:  return "REDUCE"
    return "SELL"

def _rating_color(score: float) -> str:
    if score >= 2.0:   return "positive"
    if score >= 0.5:   return "neutral"
    return "negative"


def _score_stock(quote: dict, tech: dict, news_classified: dict, sym: str) -> float:
    """Produce a composite score for a stock: range roughly -5 to +5."""
    score = 0.0

    # Price momentum
    chg = quote.get("change_pct") or 0
    score += min(max(chg / 5, -1), 1)   # clamp ±1

    # Volume confirmation
    vr = quote.get("vol_ratio") or 1
    if vr > 1.5 and chg > 0:
        score += 0.5
    elif vr > 1.5 and chg < 0:
        score -= 0.5

    # RSI
    rsi = tech.get("rsi") if not tech.get("error") else None
    if rsi is not None:
        if 40 < rsi < 65:   score += 0.5   # healthy zone
        elif rsi < 30:      score += 0.75  # oversold bounce
        elif rsi > 75:      score -= 0.75  # overbought

    # MACD histogram direction
    hist = tech.get("macd_hist") if not tech.get("error") else None
    if hist is not None:
        score += 0.5 if hist > 0 else -0.5

    # Trend vs SMA
    price  = quote.get("price") or 0
    sma50  = tech.get("sma50")
    sma200 = tech.get("sma200")
    if sma50  and price > sma50:   score += 0.5
    if sma200 and price > sma200:  score += 0.5

    # Technical signals from compute_technicals
    for sig in (tech.get("signals") or []):
        score += 0.5 if sig["type"] == "bullish" else -0.5

    # News sentiment
    sym_news = news_classified.get(sym, {})
    bull = len(sym_news.get("bullish", []))
    bear = len(sym_news.get("bearish", []))
    score += min((bull - bear) * 0.3, 1.5)

    # Options P/C ratio (contrarian: high P/C = bearish sentiment = potential bounce)
    return round(score, 2)


def generate_trading_advice(
    quotes: dict,
    technicals: dict,
    news_classified: dict,
    impact_summary: dict,
    sector_news: dict,
) -> list[dict]:
    """
    Produce structured trading advice for each watched stock.
    Returns list of advice dicts.
    """
    advice_list = []

    sector_bull = {
        s: len(sector_news.get(s, {}).get("bullish", []))
        for s in ["Aviation", "AI", "Space", "Storage"]
    }
    sector_bear = {
        s: len(sector_news.get(s, {}).get("bearish", []))
        for s in ["Aviation", "AI", "Space", "Storage"]
    }

    sector_map = {
        "RKLB": "Space",
        "NOK":  "AI",
        "CPSH": "Aviation",
    }

    for sym, name in WATCH_STOCKS.items():
        q    = quotes.get(sym, {})
        tech = technicals.get(sym, {})
        imp  = impact_summary.get(sym, {})
        sec  = sector_map.get(sym, "AI")

        score  = _score_stock(q, tech, news_classified, sym)
        rating = _rating(score)
        color  = _rating_color(score)

        price    = q.get("price")
        chg      = q.get("change_pct")
        support  = tech.get("support") if not tech.get("error") else None
        resistance = tech.get("resistance") if not tech.get("error") else None
        atr      = tech.get("atr") if not tech.get("error") else None

        # Entry / stop / target based on ATR
        entry = stop = target = None
        if price and atr:
            entry  = round(price, 4)
            stop   = round(price - 1.5 * atr, 4)
            target = round(price + 2.5 * atr, 4)

        # Build rationale
        rationale_parts = []

        # Technical rationale
        rsi = tech.get("rsi") if not tech.get("error") else None
        if rsi:
            if rsi > 70:
                rationale_parts.append(f"RSI {rsi:.0f} 超买，短线上行空间有限")
            elif rsi < 30:
                rationale_parts.append(f"RSI {rsi:.0f} 超卖，存在技术性反弹机会")
            else:
                rationale_parts.append(f"RSI {rsi:.0f} 处于健康区间")

        for sig in (tech.get("signals") or [])[:2]:
            rationale_parts.append(sig["msg"])

        # News rationale
        sym_news = news_classified.get(sym, {})
        if sym_news.get("bullish"):
            top_bull = sym_news["bullish"][0]["title"]
            rationale_parts.append(f"利好：{top_bull[:60]}…")
        if sym_news.get("bearish"):
            top_bear = sym_news["bearish"][0]["title"]
            rationale_parts.append(f"风险：{top_bear[:60]}…")

        # Sector context
        sb = sector_bull.get(sec, 0)
        se = sector_bear.get(sec, 0)
        if sb > se:
            rationale_parts.append(f"所在板块（{sec}）新闻面偏多，提供顺风支撑")
        elif se > sb:
            rationale_parts.append(f"所在板块（{sec}）新闻面偏空，存在系统性压力")

        # Flags
        flags = imp.get("flags", [])

        # Risks
        risks = []
        if chg and chg <= -3:
            risks.append("股价今日大幅下跌，动能偏弱")
        if rsi and rsi > 72:
            risks.append("技术面超买，短线回调风险")
        vr = q.get("vol_ratio") or 1
        if vr > 2.5 and chg and chg < 0:
            risks.append("放量下跌，可能是主力出货信号")
        if not risks:
            risks.append("无明显短期风险信号")

        # Time horizon
        if abs(score) > 3:
            horizon = "短线（1-3 交易日）"
        elif abs(score) > 1.5:
            horizon = "中短线（1-2 周）"
        else:
            horizon = "观望，等待方向确认"

        advice_list.append({
            "symbol":    sym,
            "name":      name,
            "score":     score,
            "rating":    rating,
            "rating_en": _rating_en(score),
            "color":     color,
            "price":     price,
            "chg":       chg,
            "entry":     entry,
            "stop":      stop,
            "target":    target,
            "horizon":   horizon,
            "rationale": rationale_parts,
            "risks":     risks,
            "flags":     flags,
        })

    return advice_list


def _quick_quote(sym: str) -> dict | None:
    """Fast single-ticker quote for the strong-stock scanner."""
    try:
        t    = yf.Ticker(sym)
        info = t.info or {}
        price     = info.get("currentPrice") or info.get("regularMarketPrice")
        prev      = info.get("previousClose") or info.get("regularMarketPreviousClose")
        volume    = info.get("volume") or info.get("regularMarketVolume")
        avg_vol   = info.get("averageVolume") or info.get("averageDailyVolume10Day")
        mktcap    = info.get("marketCap")
        pe        = info.get("trailingPE")
        fwd_pe    = info.get("forwardPE")
        peg       = info.get("pegRatio")
        short_name = info.get("shortName") or sym

        chg = round((price - prev) / prev * 100, 2) if price and prev else None
        vr  = round(volume / avg_vol, 2) if volume and avg_vol and avg_vol > 0 else None

        return {
            "symbol":    sym,
            "name":      short_name,
            "price":     price,
            "chg":       chg,
            "vol_ratio": vr,
            "mktcap":    mktcap,
            "pe":        pe,
            "fwd_pe":    fwd_pe,
            "peg":       peg,
        }
    except Exception:
        return None


def _quick_rsi(sym: str) -> float | None:
    try:
        import numpy as np
        t    = yf.Ticker(sym)
        hist = t.history(period="1mo", interval="1d")
        if hist.empty or len(hist) < 15:
            return None
        close = hist["Close"]
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, float("nan"))
        rsi   = 100 - (100 / (1 + rs))
        return round(float(rsi.iloc[-1]), 1)
    except Exception:
        return None


def scan_strong_stocks(news_classified: dict) -> list[dict]:
    """
    Scan STRONG_STOCK_UNIVERSE for today's momentum leaders.
    Criteria: price up >1.5%, volume ratio >1.3x, RSI 40-72.
    Returns top 6 sorted by composite score.
    """
    results = []
    news_scores: dict[str, int] = {}
    for sym in STRONG_STOCK_UNIVERSE:
        sym_news = news_classified.get(sym, {})
        news_scores[sym] = len(sym_news.get("bullish", [])) - len(sym_news.get("bearish", []))

    for sym in STRONG_STOCK_UNIVERSE:
        q = _quick_quote(sym)
        if not q:
            continue
        chg = q.get("chg") or 0
        vr  = q.get("vol_ratio") or 1
        if chg < 1.0 or vr < 1.2:
            continue

        rsi = _quick_rsi(sym)
        if rsi is not None and (rsi > 78 or rsi < 35):
            continue   # filter extreme values for "strong" picks

        score = chg * 0.4 + (vr - 1) * 0.3 + news_scores.get(sym, 0) * 0.3
        results.append({**q, "rsi": rsi, "score": round(score, 2)})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:6]


def scan_undervalued_stocks(news_classified: dict) -> list[dict]:
    """
    Institutional-lens scan: look for stocks with low forward P/E,
    positive news momentum, and low PEG in growth sectors.
    Returns up to 5 candidates.
    """
    results = []
    news_scores: dict[str, int] = {}
    for sym in STRONG_STOCK_UNIVERSE:
        sym_news = news_classified.get(sym, {})
        news_scores[sym] = len(sym_news.get("bullish", [])) - len(sym_news.get("bearish", []))

    for sym in STRONG_STOCK_UNIVERSE:
        q = _quick_quote(sym)
        if not q:
            continue
        fwd_pe = q.get("fwd_pe")
        peg    = q.get("peg")
        chg    = q.get("chg") or 0
        mktcap = q.get("mktcap") or 0

        # Must have valuation data
        if not fwd_pe or fwd_pe <= 0 or fwd_pe > 60:
            continue
        if mktcap < 500_000_000:   # min $500M market cap
            continue

        # Value score: lower fwd P/E + lower PEG = better
        val_score = 0.0
        if fwd_pe < 15:      val_score += 2.0
        elif fwd_pe < 25:    val_score += 1.0
        elif fwd_pe < 35:    val_score += 0.0
        else:                val_score -= 0.5

        if peg and 0 < peg < 1.0:   val_score += 1.5
        elif peg and peg < 2.0:     val_score += 0.5

        # Recent price weakness = better entry
        if -15 < chg < -2:  val_score += 0.5

        # Positive news momentum
        val_score += min(news_scores.get(sym, 0) * 0.2, 1.0)

        if val_score < 1.0:
            continue

        rsi = _quick_rsi(sym)
        results.append({**q, "rsi": rsi, "val_score": round(val_score, 2)})

    results.sort(key=lambda x: x["val_score"], reverse=True)
    return results[:5]
