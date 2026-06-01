"""Fetches real-time and intraday market data via yfinance."""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
import logging

from briefing.config import (
    WATCH_STOCKS, MARKET_INDICES, AVIATION_PEERS, AI_PEERS,
    SECTOR_ETFS, TIMEZONE,
)

log = logging.getLogger(__name__)
ET = pytz.timezone(TIMEZONE)


def _pct(new_val, old_val) -> float | None:
    try:
        return round((new_val - old_val) / old_val * 100, 2)
    except Exception:
        return None


def _safe(ticker_info: dict, *keys, default=None):
    for k in keys:
        v = ticker_info.get(k)
        if v is not None:
            return v
    return default


def fetch_quote(symbol: str) -> dict:
    """Return a rich quote dict for a single symbol."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        hist_1d = t.history(period="2d", interval="1m")
        hist_5d = t.history(period="5d", interval="1d")

        price       = _safe(info, "currentPrice", "regularMarketPrice", "ask", "bid")
        prev_close  = _safe(info, "previousClose", "regularMarketPreviousClose")
        open_price  = _safe(info, "open", "regularMarketOpen")
        day_high    = _safe(info, "dayHigh", "regularMarketDayHigh")
        day_low     = _safe(info, "dayLow", "regularMarketDayLow")
        volume      = _safe(info, "volume", "regularMarketVolume")
        avg_volume  = _safe(info, "averageVolume", "averageDailyVolume10Day")
        market_cap  = info.get("marketCap")
        week52_high = info.get("fiftyTwoWeekHigh")
        week52_low  = info.get("fiftyTwoWeekLow")
        pe_ratio    = info.get("trailingPE")
        eps         = info.get("trailingEps")
        beta        = info.get("beta")
        short_name  = info.get("shortName") or info.get("longName") or symbol

        change_pct  = _pct(price, prev_close) if price and prev_close else None

        # Volume ratio vs average
        vol_ratio = round(volume / avg_volume, 2) if volume and avg_volume and avg_volume > 0 else None

        # 5-day return
        ret_5d = None
        if not hist_5d.empty and len(hist_5d) >= 2:
            ret_5d = _pct(hist_5d["Close"].iloc[-1], hist_5d["Close"].iloc[0])

        # Intraday OHLCV (today only)
        intraday = None
        if not hist_1d.empty:
            today = datetime.now(ET).date()
            today_data = hist_1d[hist_1d.index.tz_convert(ET).date == today]
            if not today_data.empty:
                intraday = today_data[["Open", "High", "Low", "Close", "Volume"]].copy()

        return {
            "symbol":      symbol,
            "name":        short_name,
            "price":       price,
            "prev_close":  prev_close,
            "open":        open_price,
            "high":        day_high,
            "low":         day_low,
            "change_pct":  change_pct,
            "volume":      volume,
            "avg_volume":  avg_volume,
            "vol_ratio":   vol_ratio,
            "market_cap":  market_cap,
            "52w_high":    week52_high,
            "52w_low":     week52_low,
            "pe":          pe_ratio,
            "eps":         eps,
            "beta":        beta,
            "ret_5d":      ret_5d,
            "intraday":    intraday,
            "ts":          datetime.now(ET),
        }
    except Exception as e:
        log.warning("fetch_quote(%s) failed: %s", symbol, e)
        return {"symbol": symbol, "error": str(e)}


def fetch_all_quotes() -> dict:
    """Return quotes for all tracked symbols (watch + indices + ETFs + peers)."""
    all_symbols = (
        list(WATCH_STOCKS.keys())
        + list(MARKET_INDICES.keys())
        + [s for etfs in SECTOR_ETFS.values() for s in etfs]
        + AVIATION_PEERS
        + AI_PEERS
    )
    results = {}
    for sym in dict.fromkeys(all_symbols):   # preserve order, deduplicate
        results[sym] = fetch_quote(sym)
    return results


def fetch_options_snapshot(symbol: str) -> dict | None:
    """Return nearest-expiry options chain summary for sentiment."""
    try:
        t = yf.Ticker(symbol)
        expiries = t.options
        if not expiries:
            return None
        chain = t.option_chain(expiries[0])
        calls = chain.calls
        puts  = chain.puts

        total_call_oi = int(calls["openInterest"].sum()) if "openInterest" in calls else 0
        total_put_oi  = int(puts["openInterest"].sum())  if "openInterest" in puts  else 0
        put_call = round(total_put_oi / total_call_oi, 3) if total_call_oi else None

        # Highest OI strikes
        top_call_strike = calls.nlargest(1, "openInterest")["strike"].values[0] if not calls.empty else None
        top_put_strike  = puts.nlargest(1, "openInterest")["strike"].values[0]  if not puts.empty  else None

        return {
            "expiry":          expiries[0],
            "call_oi":         total_call_oi,
            "put_oi":          total_put_oi,
            "put_call_ratio":  put_call,
            "top_call_strike": top_call_strike,
            "top_put_strike":  top_put_strike,
        }
    except Exception as e:
        log.debug("fetch_options_snapshot(%s): %s", symbol, e)
        return None


def fetch_earnings_calendar() -> list[dict]:
    """Return upcoming earnings for watched stocks (best-effort from yfinance)."""
    upcoming = []
    for sym in WATCH_STOCKS:
        try:
            t = yf.Ticker(sym)
            cal = t.calendar
            if cal is not None and not cal.empty:
                # calendar is a DataFrame with dates as columns
                dates = cal.columns.tolist()
                upcoming.append({"symbol": sym, "dates": [str(d) for d in dates]})
        except Exception:
            pass
    return upcoming
