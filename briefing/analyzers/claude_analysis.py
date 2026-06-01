"""
LLM-powered deep analysis using Claude API (claude-sonnet-4-6).
Falls back gracefully when ANTHROPIC_API_KEY is not set.
Uses prompt caching on the stable system prompt to save tokens.
"""
from __future__ import annotations
import json
import logging
import os

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一位专业的美股投资分析师，精通技术分析、基本面分析和市场动态。
你的任务是根据提供的实时数据，为指定股票生成中文深度分析报告。

分析要求：
1. 综合摘要：100字以内，描述今日整体表现和市场情绪
2. 技术面分析：结合RSI、MACD、均线、成交量，给出简明技术判断
3. 利好因素：从新闻中提炼2-4条最重要的利好，每条25字以内
4. 利空因素：从新闻中提炼2-4条最重要的利空，每条25字以内
5. 短线展望（1-3天）：明确给出"偏多"/"偏空"/"观望"及理由
6. 关键价位：支撑位和阻力位

输出格式要求：
- 以 JSON 格式输出，字段名为：summary, tech_narrative, bull_points(list), bear_points(list), outlook, key_levels(list), overall("多头"/"空头"/"中性")
- 语言：简体中文
- 风格：专业简洁，避免废话
- 不要输出 JSON 以外的任何内容
"""


def _build_user_message(symbol: str, name: str, quote: dict, tech: dict,
                        bull_news: list, bear_news: list) -> str:
    price    = quote.get("price")
    chg      = quote.get("change_pct")
    volume   = quote.get("volume")
    vol_ratio = quote.get("vol_ratio")
    pe       = quote.get("pe")
    beta     = quote.get("beta")
    w52h     = quote.get("52w_high")
    w52l     = quote.get("52w_low")

    rsi      = tech.get("rsi")
    macd     = tech.get("macd")
    macd_sig = tech.get("macd_signal")
    macd_hist = tech.get("macd_hist")
    sma50    = tech.get("sma50")
    sma200   = tech.get("sma200")
    support  = tech.get("support")
    resistance = tech.get("resistance")
    trend    = tech.get("trend", "")
    signals  = tech.get("signals", [])

    def _fmt(v, decimals=2):
        try:
            return round(float(v), decimals)
        except (TypeError, ValueError):
            return None

    data = {
        "symbol": symbol,
        "name": name,
        "quote": {
            "price":      _fmt(price, 4),
            "change_pct": _fmt(chg, 2),
            "volume":     int(volume) if volume else None,
            "vol_ratio":  _fmt(vol_ratio, 2),
            "pe":         _fmt(pe, 2),
            "beta":       _fmt(beta, 2),
            "52w_high":   _fmt(w52h, 2),
            "52w_low":    _fmt(w52l, 2),
        },
        "technicals": {
            "rsi":        _fmt(rsi, 1),
            "macd":       _fmt(macd, 4),
            "macd_signal": _fmt(macd_sig, 4),
            "macd_hist":  _fmt(macd_hist, 4),
            "sma50":      _fmt(sma50, 2),
            "sma200":     _fmt(sma200, 2),
            "support":    _fmt(support, 4),
            "resistance": _fmt(resistance, 4),
            "trend":      trend,
            "signals":    [{"type": s.get("type"), "msg": s.get("msg")} for s in signals],
        },
        "bullish_news": [
            {"title": a.get("title", ""), "source": a.get("source", ""), "impact": a.get("impact", "")}
            for a in bull_news[:6]
        ],
        "bearish_news": [
            {"title": a.get("title", ""), "source": a.get("source", ""), "impact": a.get("impact", "")}
            for a in bear_news[:6]
        ],
    }

    return f"请分析以下股票数据：\n\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"


def _parse_response(text: str) -> dict:
    """Extract JSON from Claude's response, robust to markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object boundaries
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


def build_claude_analysis(
    symbol: str,
    name: str,
    quote: dict,
    tech: dict,
    bull_news: list,
    bear_news: list,
) -> dict | None:
    """
    Call Claude API to generate deep analysis.
    Returns a dict compatible with build_deep_analysis() output,
    or None if the API is unavailable or fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        log.warning("anthropic package not installed; skipping Claude analysis")
        return None

    user_msg = _build_user_message(symbol, name, quote, tech, bull_news, bear_news)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = response.content[0].text if response.content else ""
        result = _parse_response(raw)

        # Normalise to expected shape
        return {
            "summary":        result.get("summary", ""),
            "tech_narrative": result.get("tech_narrative", ""),
            "bull_points":    result.get("bull_points", []),
            "bear_points":    result.get("bear_points", []),
            "outlook":        result.get("outlook", ""),
            "key_levels":     result.get("key_levels", []),
            "overall":        result.get("overall", "中性"),
        }

    except Exception as e:
        log.warning("Claude analysis failed for %s: %s", symbol, e)
        return None


def build_all_claude_analyses(
    watch_stocks: dict,
    quotes: dict,
    technicals: dict,
    news_classified: dict,
) -> dict:
    """
    Run Claude analysis for every watch stock.
    Returns dict keyed by symbol; value is analysis dict or None.
    """
    results = {}
    for sym, name in watch_stocks.items():
        q        = quotes.get(sym, {})
        tech     = technicals.get(sym, {})
        sym_news = news_classified.get(sym, {})
        log.info("  Claude analysis: %s …", sym)
        results[sym] = build_claude_analysis(
            symbol=sym,
            name=name,
            quote=q,
            tech=tech,
            bull_news=sym_news.get("bullish", []),
            bear_news=sym_news.get("bearish", []),
        )
    return results
