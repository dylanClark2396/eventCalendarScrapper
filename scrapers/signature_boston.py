"""
Scraper for Signature Boston (BCEC / Hynes) event calendar.
https://www.signatureboston.com/events
"""

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "signature_boston"
CALENDAR_NAME = "Signature Boston"
BASE_URL = "https://www.signatureboston.com/events"
MONTHS_AHEAD = 6

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def fetch_month(year: int, month: int) -> list[dict]:
    url = f"{BASE_URL}/{year}-{month:02d}-01"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    for li in soup.find_all("li"):
        h4 = li.find("h4", class_="event-list__title")
        if not h4:
            continue
        title = h4.get_text(strip=True)
        if not title:
            continue

        date_el = li.find("li", class_="info__dates")
        date_str = date_el.get_text(strip=True) if date_el else ""

        venue_el = li.find("li", class_="info__location")
        venue = venue_el.get_text(strip=True) if venue_el else ""

        a = h4.find("a")
        link = a.get("href", "") if a else ""

        events.append({
            "title": title,
            "date": date_str,
            "description": venue,
            "link": link,
        })

    return events


def fetch_events() -> list[dict]:
    all_events = []
    seen = set()
    now = datetime.now(timezone.utc)

    for i in range(MONTHS_AHEAD):
        target = now + relativedelta(months=i)
        month_events = fetch_month(target.year, target.month)
        for e in month_events:
            key = (e["title"], e["date"])
            if key not in seen:
                seen.add(key)
                all_events.append(e)

    return all_events
