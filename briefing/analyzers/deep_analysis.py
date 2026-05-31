"""
Deep per-stock narrative analysis combining news, technicals, and fundamentals.
Produces structured text summaries — no LLM required.
"""
from __future__ import annotations
from datetime import datetime, timezone


def _trend_word(chg: float | None) -> str:
    if chg is None:
        return "持平"
    if chg >= 5:   return "强势上涨"
    if chg >= 2:   return "温和上涨"
    if chg >= 0:   return "小幅上涨"
    if chg >= -2:  return "小幅下跌"
    if chg >= -5:  return "温和下跌"
    return "大幅下跌"


def _rsi_interpretation(rsi: float | None) -> str:
    if rsi is None:
        return "RSI数据不可用"
    if rsi >= 80:  return f"RSI {rsi:.0f}，严重超买，短期回调风险高"
    if rsi >= 70:  return f"RSI {rsi:.0f}，进入超买区间，上行动能趋缓"
    if rsi >= 55:  return f"RSI {rsi:.0f}，多头占优，动能健康"
    if rsi >= 45:  return f"RSI {rsi:.0f}，多空均衡，方向待确认"
    if rsi >= 30:  return f"RSI {rsi:.0f}，空头主导，但尚未超卖"
    if rsi >= 20:  return f"RSI {rsi:.0f}，进入超卖区间，存在反弹机会"
    return f"RSI {rsi:.0f}，严重超卖，技术性反弹概率高"


def _volume_interpretation(vol_ratio: float | None) -> str:
    if vol_ratio is None:
        return ""
    if vol_ratio >= 3.0:  return f"量比 {vol_ratio:.1f}x，异常放量，需警惕主力动向"
    if vol_ratio >= 2.0:  return f"量比 {vol_ratio:.1f}x，明显放量，资金入场信号"
    if vol_ratio >= 1.3:  return f"量比 {vol_ratio:.1f}x，温和放量，方向确认中"
    if vol_ratio >= 0.7:  return f"量比 {vol_ratio:.1f}x，成交量正常"
    return f"量比 {vol_ratio:.1f}x，缩量，市场观望情绪浓"


def _macd_interpretation(macd: float | None, signal: float | None, hist: float | None) -> str:
    if macd is None or signal is None:
        return ""
    if macd > signal and (hist or 0) > 0:
        return "MACD金叉且柱状图为正，短期动能向上"
    if macd > signal and (hist or 0) <= 0:
        return "MACD在信号线上方但柱状图收缩，上行动能趋弱"
    if macd < signal and (hist or 0) < 0:
        return "MACD死叉且柱状图为负，短期动能向下"
    return "MACD在信号线下方但柱状图收缩，下行动能趋弱"


def _news_narrative(bull_news: list, bear_news: list) -> tuple[list[str], list[str]]:
    """Convert news lists into clean bullet-point narrative strings."""
    bull_pts = []
    for a in bull_news[:6]:
        title   = a.get("title", "").strip()
        source  = a.get("source", "")
        pub     = a.get("published")
        ts      = pub.strftime("%m-%d %H:%M") if pub else ""
        impact  = a.get("impact", "")
        tag     = f"[{impact}]" if impact else ""
        bull_pts.append(f"{tag} {title}（{source}{', ' + ts if ts else ''}）")

    bear_pts = []
    for a in bear_news[:6]:
        title   = a.get("title", "").strip()
        source  = a.get("source", "")
        pub     = a.get("published")
        ts      = pub.strftime("%m-%d %H:%M") if pub else ""
        impact  = a.get("impact", "")
        tag     = f"[{impact}]" if impact else ""
        bear_pts.append(f"{tag} {title}（{source}{', ' + ts if ts else ''}）")

    return bull_pts, bear_pts


def _52w_position(price, w52h, w52l) -> str:
    try:
        pct_from_low  = (price - w52l) / (w52h - w52l) * 100
        if pct_from_low >= 90:
            return f"价格处于52周高位区（位置 {pct_from_low:.0f}%），估值偏高需谨慎"
        if pct_from_low >= 60:
            return f"价格处于52周中高位区（位置 {pct_from_low:.0f}%）"
        if pct_from_low >= 30:
            return f"价格处于52周中低位区（位置 {pct_from_low:.0f}%），具有修复空间"
        return f"价格处于52周低位区（位置 {pct_from_low:.0f}%），存在超跌反弹机会"
    except Exception:
        return ""


def build_deep_analysis(
    symbol: str,
    quote: dict,
    tech: dict,
    bull_news: list,
    bear_news: list,
) -> dict:
    """
    Return a structured deep analysis dict with:
      - summary: one-paragraph overall assessment
      - bull_points: list of bullish narrative bullets
      - bear_points: list of bearish narrative bullets
      - tech_narrative: technical picture paragraph
      - outlook: short-term directional view
      - key_levels: support / resistance strings
    """
    price     = quote.get("price")
    chg       = quote.get("change_pct")
    vol_ratio = quote.get("vol_ratio")
    w52h      = quote.get("52w_high")
    w52l      = quote.get("52w_low")
    pe        = quote.get("pe")
    beta      = quote.get("beta")

    rsi      = tech.get("rsi")   if not tech.get("error") else None
    macd     = tech.get("macd")  if not tech.get("error") else None
    signal   = tech.get("macd_signal") if not tech.get("error") else None
    hist     = tech.get("macd_hist")   if not tech.get("error") else None
    trend    = tech.get("trend", "")
    signals  = tech.get("signals", [])
    support  = tech.get("support")
    resistance = tech.get("resistance")
    sma50    = tech.get("sma50")
    sma200   = tech.get("sma200")

    bull_pts, bear_pts = _news_narrative(bull_news, bear_news)

    # ── Technical narrative ────────────────────────────────────────────
    tech_parts = []
    if rsi is not None:
        tech_parts.append(_rsi_interpretation(rsi))
    if macd is not None:
        macd_str = _macd_interpretation(macd, signal, hist)
        if macd_str:
            tech_parts.append(macd_str)
    vol_str = _volume_interpretation(vol_ratio)
    if vol_str:
        tech_parts.append(vol_str)
    if price and sma50:
        above = price > sma50
        tech_parts.append(f"价格{'高于' if above else '低于'} 50日均线（SMA50: {sma50:.2f}），{'中期趋势偏多' if above else '中期趋势偏空'}")
    if price and sma200:
        above = price > sma200
        tech_parts.append(f"价格{'高于' if above else '低于'} 200日均线（SMA200: {sma200:.2f}），{'长期牛市结构' if above else '长期熊市结构'}")
    if signals:
        for sig in signals:
            tech_parts.append(f"{'▲' if sig['type']=='bullish' else '▼'} 技术信号：{sig['msg']}")
    if w52h and w52l and price:
        pos_str = _52w_position(price, w52h, w52l)
        if pos_str:
            tech_parts.append(pos_str)

    tech_narrative = "；".join(tech_parts) + "。" if tech_parts else "技术数据暂不可用。"

    # ── Key levels ─────────────────────────────────────────────────────
    levels = []
    if support:
        levels.append(f"支撑位 ${support:.4f}")
    if resistance:
        levels.append(f"阻力位 ${resistance:.4f}")
    if sma50:
        levels.append(f"SMA50 ${sma50:.2f}")
    if w52h:
        levels.append(f"52周高点 ${w52h:.2f}")
    if w52l:
        levels.append(f"52周低点 ${w52l:.2f}")

    # ── Overall summary ────────────────────────────────────────────────
    bull_count = len(bull_pts)
    bear_count = len(bear_pts)
    trend_desc = _trend_word(chg)

    if bull_count > bear_count and (rsi or 50) < 70:
        overall = "多头"
        outlook = "短期偏多，建议关注放量突破信号"
    elif bear_count > bull_count or (rsi or 50) > 75:
        overall = "空头"
        outlook = "短期偏空，建议控制仓位，等待企稳信号"
    else:
        overall = "中性"
        outlook = "方向不明，建议观望，等待催化剂出现"

    pe_str = f"，市盈率 {pe:.1f}x" if pe else ""
    beta_str = f"，Beta {beta:.2f}（{'高波动' if beta and beta > 1.5 else '低波动' if beta and beta < 0.8 else '中等波动'}）" if beta else ""

    summary = (
        f"{symbol} 今日{trend_desc}（{'+' if (chg or 0)>=0 else ''}{chg:.2f}%）"
        if chg else f"{symbol} 今日行情数据暂不可用"
    )
    summary += f"{pe_str}{beta_str}。"
    summary += f"新闻面{bull_count}条利好、{bear_count}条利空，整体偏{overall}。"

    return {
        "summary":        summary,
        "tech_narrative": tech_narrative,
        "bull_points":    bull_pts,
        "bear_points":    bear_pts,
        "outlook":        outlook,
        "key_levels":     levels,
        "overall":        overall,
    }
