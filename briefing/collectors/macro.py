"""Macro data: economic calendar, Fed watch, yield curve, fear & greed."""
import requests
import logging
from datetime import datetime, date, timedelta
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_economic_calendar() -> list[dict]:
    """Scrape today's + next-2-days economic events from Trading Economics."""
    events = []
    try:
        url = "https://tradingeconomics.com/calendar"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        rows = soup.select("tr.calendar-item")
        today = date.today()
        cutoff = today + timedelta(days=3)

        for row in rows[:60]:
            try:
                date_td  = row.select_one("td.calendar-date")
                time_td  = row.select_one("td.calendar-time")
                country  = row.select_one("td.calendar-country")
                event_td = row.select_one("td.calendar-event a")
                actual   = row.select_one("td.calendar-actual")
                forecast = row.select_one("td.calendar-forecast")
                previous = row.select_one("td.calendar-previous")
                impact   = row.select_one("td.calendar-impact span")

                raw_date = date_td.get_text(strip=True) if date_td else ""
                if not raw_date:
                    continue
                try:
                    ev_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if ev_date < today or ev_date > cutoff:
                    continue

                events.append({
                    "date":     ev_date.isoformat(),
                    "time":     time_td.get_text(strip=True) if time_td else "",
                    "country":  country.get_text(strip=True) if country else "",
                    "event":    event_td.get_text(strip=True) if event_td else "",
                    "actual":   actual.get_text(strip=True)   if actual   else "",
                    "forecast": forecast.get_text(strip=True) if forecast else "",
                    "previous": previous.get_text(strip=True) if previous else "",
                    "impact":   impact.get("class", [""])[0]  if impact   else "",
                })
            except Exception:
                continue
    except Exception as e:
        log.warning("Economic calendar fetch failed: %s", e)

    # Filter to US high-impact events
    us_events = [
        e for e in events
        if e["country"].upper() in ("US", "USD", "UNITED STATES", "") or
           any(kw in e["event"].upper() for kw in [
               "FED", "FOMC", "CPI", "PPI", "GDP", "NFP", "NONFARM",
               "UNEMPLOYMENT", "RETAIL SALES", "ISM", "PMI", "TREASURY",
               "JEROME POWELL", "CONSUMER PRICE", "PRODUCER PRICE",
           ])
    ]
    return us_events or events[:15]  # fallback to raw list if filter is too strict


def fetch_fear_greed() -> dict | None:
    """Fetch CNN Fear & Greed Index."""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=10)
        data = r.json()
        fg = data.get("fear_and_greed", {})
        return {
            "score":      fg.get("score"),
            "rating":     fg.get("rating"),
            "prev_1w":    data.get("fear_and_greed_historical", {}).get("data", [{}])[-7]["y"] if data.get("fear_and_greed_historical") else None,
            "prev_1m":    data.get("fear_and_greed_historical", {}).get("data", [{}])[-30]["y"] if data.get("fear_and_greed_historical") else None,
        }
    except Exception as e:
        log.debug("Fear & Greed fetch failed: %s", e)
        return None


def fetch_yield_curve() -> dict | None:
    """Fetch US Treasury yields via yfinance proxies."""
    try:
        import yfinance as yf
        # Mapping: treasury ETF/symbol → maturity label
        symbols = {
            "^IRX": "3M",
            "^FVX": "5Y",
            "^TNX": "10Y",
            "^TYX": "30Y",
        }
        yields = {}
        for sym, label in symbols.items():
            try:
                t = yf.Ticker(sym)
                info = t.info
                price = info.get("regularMarketPrice") or info.get("ask")
                if price:
                    yields[label] = round(float(price), 3)
            except Exception:
                pass

        if yields:
            spread_10_2 = None
            # Approximate 2Y from 3M and 5Y if needed
            if "10Y" in yields and "3M" in yields:
                spread_10_2 = round(yields["10Y"] - yields["3M"], 3)
            return {
                "yields": yields,
                "10Y_3M_spread": spread_10_2,
                "inverted": (spread_10_2 is not None and spread_10_2 < 0),
            }
    except Exception as e:
        log.debug("Yield curve fetch failed: %s", e)
    return None
