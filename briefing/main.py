"""
Main orchestrator for the US Stock Daily Briefing.

Sessions:
  pre_market   — 07:30 ET   Pre-market overview
  open         — 09:35 ET   Market open snapshot
  midday       — 12:00 ET   Midday update
  close        — 16:05 ET   Close / after-hours summary
  after_hours  — 17:30 ET   After-hours movers
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
import time
from datetime import datetime

import pytz
import schedule

from briefing.config import WATCH_STOCKS, SCHEDULE_TIMES, TIMEZONE
from briefing.collectors.market_data import fetch_all_quotes, fetch_options_snapshot, fetch_earnings_calendar
from briefing.collectors.news import fetch_all_news
from briefing.collectors.macro import fetch_economic_calendar, fetch_fear_greed, fetch_yield_curve
from briefing.analyzers.technicals import compute_technicals
from briefing.analyzers.impact import classify_articles, summarize_market_impact
from briefing.analyzers.deep_analysis import build_deep_analysis
from briefing.analyzers.claude_analysis import build_all_claude_analyses
from briefing.analyzers.trading_advice import (
    generate_trading_advice, scan_strong_stocks, scan_undervalued_stocks
)
from briefing.reporters.html_report import generate_html
from briefing.reporters.email_sender import send_email

ET = pytz.timezone(TIMEZONE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("briefing.main")


def _session_from_time() -> str:
    now = datetime.now(ET)
    h, m = now.hour, now.minute
    t = h * 60 + m
    if   t < 9 * 60 + 35:  return "pre_market"
    elif t < 12 * 60:       return "open"
    elif t < 16 * 60 + 5:  return "midday"
    elif t < 17 * 60 + 30: return "close"
    else:                    return "after_hours"


def run_briefing(session: str | None = None) -> str:
    session = session or _session_from_time()
    log.info("=== Starting %s briefing ===", session)
    start = time.time()

    # ── 1. Collect market data ────────────────────────────────────────────────
    log.info("Fetching quotes …")
    quotes = fetch_all_quotes()

    # ── 2. Collect news ───────────────────────────────────────────────────────
    log.info("Fetching news …")
    articles = fetch_all_news()
    log.info("  %d relevant articles collected", len(articles))

    # ── 3. Technical analysis ─────────────────────────────────────────────────
    log.info("Computing technicals …")
    technicals = {sym: compute_technicals(sym) for sym in WATCH_STOCKS}

    # ── 4. Options snapshots ──────────────────────────────────────────────────
    log.info("Fetching options …")
    options_data = {sym: fetch_options_snapshot(sym) for sym in WATCH_STOCKS}

    # ── 5. Earnings calendar ──────────────────────────────────────────────────
    earnings = fetch_earnings_calendar()

    # ── 6. Macro ──────────────────────────────────────────────────────────────
    log.info("Fetching macro data …")
    macro_data = {
        "calendar":   fetch_economic_calendar(),
        "fear_greed": fetch_fear_greed(),
        "yield_curve": fetch_yield_curve(),
    }

    # ── 7. Impact analysis ────────────────────────────────────────────────────
    log.info("Classifying news impact …")
    news_classified = classify_articles(articles)
    impact_summary  = summarize_market_impact(quotes, news_classified)

    # ── 8. Deep per-stock analysis (Claude API → rule-based fallback) ─────────
    log.info("Building deep analysis …")
    claude_results = build_all_claude_analyses(
        watch_stocks=WATCH_STOCKS,
        quotes=quotes,
        technicals=technicals,
        news_classified=news_classified,
    )
    deep_analysis = {}
    for sym in WATCH_STOCKS:
        if claude_results.get(sym):
            log.info("  Using Claude analysis for %s", sym)
            deep_analysis[sym] = claude_results[sym]
        else:
            log.info("  Falling back to rule-based analysis for %s", sym)
            q        = quotes.get(sym, {})
            tech     = technicals.get(sym, {})
            sym_news = news_classified.get(sym, {})
            deep_analysis[sym] = build_deep_analysis(
                symbol=sym,
                quote=q,
                tech=tech,
                bull_news=sym_news.get("bullish", []),
                bear_news=sym_news.get("bearish", []),
            )

    # ── 9. Trading advice + stock scans ───────────────────────────────────────
    log.info("Generating trading advice …")
    trading_advice = generate_trading_advice(
        quotes=quotes,
        technicals=technicals,
        news_classified=news_classified,
        impact_summary=impact_summary,
        sector_news=news_classified,
    )
    log.info("Scanning strong stocks …")
    strong_stocks = scan_strong_stocks(news_classified)
    log.info("Scanning undervalued stocks …")
    undervalued_stocks = scan_undervalued_stocks(news_classified)

    # ── 10. Render report ─────────────────────────────────────────────────────
    log.info("Rendering HTML report …")
    report_path = generate_html(
        session=session,
        quotes=quotes,
        news_classified=news_classified,
        technicals=technicals,
        impact_summary=impact_summary,
        macro_data=macro_data,
        options_data=options_data,
        earnings=earnings,
        deep_analysis=deep_analysis,
        trading_advice=trading_advice,
        strong_stocks=strong_stocks,
        undervalued_stocks=undervalued_stocks,
    )

    # ── 9. Email delivery ─────────────────────────────────────────────────────
    if os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"):
        log.info("Sending email …")
        send_email(report_path, session)

    elapsed = time.time() - start
    log.info("=== Briefing complete: %s  (%.1fs) ===", report_path, elapsed)
    print(f"\n✅  Report saved to: {report_path}\n")
    return report_path


def _schedule_all() -> None:
    """Register daily jobs for every session window."""
    for session, t_str in SCHEDULE_TIMES.items():
        schedule.every().monday.at(t_str).do(run_briefing, session=session)
        schedule.every().tuesday.at(t_str).do(run_briefing, session=session)
        schedule.every().wednesday.at(t_str).do(run_briefing, session=session)
        schedule.every().thursday.at(t_str).do(run_briefing, session=session)
        schedule.every().friday.at(t_str).do(run_briefing, session=session)
        log.info("Scheduled %s at %s ET (Mon–Fri)", session, t_str)

    log.info("Scheduler running. Next job: %s", schedule.next_run())
    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(
        description="US Stock Daily Briefing — 美股每日简报"
    )
    sub = parser.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="Generate briefing now")
    run_p.add_argument(
        "--session",
        choices=["pre_market", "open", "midday", "close", "after_hours"],
        help="Force a specific session label (default: auto-detect)",
    )

    sub.add_parser("schedule", help="Run as a daemon, firing on market schedule")
    args = parser.parse_args()

    if args.cmd == "run" or args.cmd is None:
        session = getattr(args, "session", None)
        run_briefing(session=session)
    elif args.cmd == "schedule":
        _schedule_all()


if __name__ == "__main__":
    main()
