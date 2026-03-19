"""
Scraper for Georgia World Congress Center event calendar.
https://www.gwcca.org/event-calendar
Direct site returns 403 (Cloudflare). Uses conventioncalendar.com as data source.
"""

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "gwcca"
CALENDAR_NAME = "Georgia World Congress Center"
BASE_URL = "https://conventioncalendar.com/us/ga/atlanta/georgia-world-congress-center"
MONTHS_AHEAD = 12

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def fetch_month(year: int, month: int) -> list[dict]:
    url = f"{BASE_URL}?date={year}-{month:02d}-01"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    for h5 in soup.find_all("h5"):
        a = h5.find("a", href=lambda h: h and "conventioncalendar.com" in h)
        if not a:
            continue
        title = a.get_text(strip=True)
        link = a.get("href", "")
        if not title:
            continue

        date_el = h5.find_next_sibling("p")
        date_str = date_el.get_text(strip=True) if date_el else ""

        events.append({
            "title": title,
            "date": date_str,
            "description": "",
            "link": link,
        })

    return events


def fetch_events() -> list[dict]:
    all_events = []
    seen = set()
    now = datetime.now(timezone.utc)

    for i in range(MONTHS_AHEAD):
        target = now + relativedelta(months=i)
        for e in fetch_month(target.year, target.month):
            key = (e["title"], e["date"])
            if key not in seen:
                seen.add(key)
                all_events.append(e)

    return all_events
