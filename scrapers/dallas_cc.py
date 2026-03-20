"""
Scraper for Kay Bailey Hutchison Convention Center event calendar.
https://www.dallasconventioncenter.com/events
"""

import re

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "dallas_cc"
CALENDAR_NAME = "Kay Bailey Hutchison Convention Center"
CALENDAR_URL = "https://www.dallasconventioncenter.com/events"
BASE_URL = "https://www.dallasconventioncenter.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

DATE_RE = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z.]*'
    r'\s+\d{1,2}(?:\s*[-–]\s*(?:\w+\s+)?\d{1,2})?,?\s*\d{4}',
    re.IGNORECASE,
)


def _find_date(container) -> str:
    """Try common date element classes, then fall back to regex on text."""
    for cls in ("event-date", "date", "dates", "event-dates"):
        el = container.find(class_=cls)
        if el:
            return el.get_text(strip=True)
    m = DATE_RE.search(container.get_text(separator=" "))
    return m.group(0).strip() if m else ""


def fetch_events() -> list[dict]:
    response = requests.get(CALENDAR_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=lambda h: h and "/events/detail/" in h)
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title or title in seen:
            continue
        seen.add(title)

        link = a.get("href", "")
        if link and not link.startswith("http"):
            link = BASE_URL + link

        date_str = _find_date(h3.parent) if h3.parent else ""

        events.append({
            "title": title,
            "date": date_str,
            "description": "",
            "link": link,
        })

    return events
