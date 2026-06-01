"""Technical indicator calculations for tracked stocks."""
import pandas as pd
import numpy as np
import yfinance as yf
import logging

log = logging.getLogger(__name__)


def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(n).mean()
    loss  = (-delta.clip(upper=0)).rolling(n).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series):
    fast = _ema(series, 12)
    slow = _ema(series, 26)
    macd_line   = fast - slow
    signal_line = _ema(macd_line, 9)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger(series: pd.Series, n: int = 20, k: float = 2.0):
    mid   = series.rolling(n).mean()
    std   = series.rolling(n).std()
    upper = mid + k * std
    lower = mid - k * std
    return upper, mid, lower


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _support_resistance(close: pd.Series, window: int = 20) -> tuple[float | None, float | None]:
    """Simple pivot-based S/R: last window's high/low."""
    if len(close) < window:
        return None, None
    recent = close.iloc[-window:]
    return float(recent.min()), float(recent.max())


def compute_technicals(symbol: str, period: str = "6mo") -> dict:
    """Return a full technical analysis dict for a symbol."""
    try:
        t    = yf.Ticker(symbol)
        hist = t.history(period=period, interval="1d")
        if hist.empty or len(hist) < 30:
            return {"symbol": symbol, "error": "insufficient history"}

        close  = hist["Close"]
        high   = hist["High"]
        low    = hist["Low"]
        volume = hist["Volume"]

        rsi_series               = _rsi(close)
        macd_line, signal, macd_hist = _macd(close)
        upper_bb, mid_bb, lower_bb   = _bollinger(close)
        atr_series                   = _atr(high, low, close)
        support, resistance          = _support_resistance(close)

        ema9   = _ema(close, 9)
        ema21  = _ema(close, 21)
        sma50  = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()

        last_close  = float(close.iloc[-1])
        last_rsi    = float(rsi_series.iloc[-1])
        last_macd   = float(macd_line.iloc[-1])
        last_signal = float(signal.iloc[-1])
        last_hist   = float(macd_hist.iloc[-1])
        last_atr    = float(atr_series.iloc[-1])
        last_ema9   = float(ema9.iloc[-1])
        last_ema21  = float(ema21.iloc[-1])
        last_sma50  = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else None
        last_sma200 = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else None

        # Signal generation
        signals = []
        if last_rsi > 70:
            signals.append({"type": "bearish", "msg": f"RSI {last_rsi:.1f} — overbought"})
        elif last_rsi < 30:
            signals.append({"type": "bullish", "msg": f"RSI {last_rsi:.1f} — oversold"})

        if last_macd > last_signal and float(macd_hist.iloc[-2]) < 0:
            signals.append({"type": "bullish", "msg": "MACD bullish crossover"})
        elif last_macd < last_signal and float(macd_hist.iloc[-2]) > 0:
            signals.append({"type": "bearish", "msg": "MACD bearish crossover"})

        if last_close > float(upper_bb.iloc[-1]):
            signals.append({"type": "bearish", "msg": "Price above upper Bollinger Band"})
        elif last_close < float(lower_bb.iloc[-1]):
            signals.append({"type": "bullish", "msg": "Price below lower Bollinger Band"})

        if last_sma50 and last_sma200:
            if last_sma50 > last_sma200 and float(sma50.iloc[-2]) <= float(sma200.iloc[-2]):
                signals.append({"type": "bullish", "msg": "Golden Cross (50 > 200 SMA)"})
            elif last_sma50 < last_sma200 and float(sma50.iloc[-2]) >= float(sma200.iloc[-2]):
                signals.append({"type": "bearish", "msg": "Death Cross (50 < 200 SMA)"})

        # Trend summary
        if last_ema9 > last_ema21:
            trend = "bullish (short-term)"
        elif last_ema9 < last_ema21:
            trend = "bearish (short-term)"
        else:
            trend = "neutral"
        if last_sma50 and last_close > last_sma50:
            trend += " | above 50-SMA"
        elif last_sma50:
            trend += " | below 50-SMA"

        return {
            "symbol":        symbol,
            "price":         last_close,
            "rsi":           round(last_rsi, 2),
            "macd":          round(last_macd, 4),
            "macd_signal":   round(last_signal, 4),
            "macd_hist":     round(last_hist, 4),
            "atr":           round(last_atr, 4),
            "ema9":          round(last_ema9, 4),
            "ema21":         round(last_ema21, 4),
            "sma50":         round(last_sma50, 4) if last_sma50 else None,
            "sma200":        round(last_sma200, 4) if last_sma200 else None,
            "bb_upper":      round(float(upper_bb.iloc[-1]), 4),
            "bb_mid":        round(float(mid_bb.iloc[-1]), 4),
            "bb_lower":      round(float(lower_bb.iloc[-1]), 4),
            "support":       round(support, 4) if support else None,
            "resistance":    round(resistance, 4) if resistance else None,
            "trend":         trend,
            "signals":       signals,
        }
    except Exception as e:
        log.warning("compute_technicals(%s): %s", symbol, e)
        return {"symbol": symbol, "error": str(e)}
