"""
Scraper for Los Angeles Convention Center event calendar.
https://www.laconventioncenter.com/events
"""

import re

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "lacc"
CALENDAR_NAME = "Los Angeles Convention Center"
CALENDAR_URL = "https://www.laconventioncenter.com/events"
BASE_URL = "https://www.laconventioncenter.com"

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


PER_PAGE = 6
AJAX_URL = BASE_URL + "/events/events_ajax/{offset}?category=0&venue=0&team=0&exclude=&per_page={per_page}&came_from_page=event-list-page"


def _parse_page(html: str, events: list, seen: set) -> int:
    """Parse one AJAX page of HTML, append new events, return count added."""
    soup = BeautifulSoup(html, "html.parser")
    added = 0
    for h3 in soup.find_all("h3"):
        # AJAX response: <a href="/events/detail/..."><h3>title</h3></a>
        a = h3.parent if h3.parent and h3.parent.name == "a" else None
        if a is None or "/events/detail/" not in (a.get("href") or ""):
            continue
        title = h3.get_text(strip=True)
        if not title or title in seen:
            continue
        seen.add(title)
        link = a.get("href", "")
        if link and not link.startswith("http"):
            link = BASE_URL + link
        date_str = _find_date(a.parent) if a.parent else ""
        events.append({"title": title, "date": date_str, "description": "", "link": link})
        added += 1
    return added


def fetch_events() -> list[dict]:
    events = []
    seen = set()
    offset = 0

    while True:
        url = AJAX_URL.format(offset=offset, per_page=PER_PAGE)
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        added = _parse_page(response.text, events, seen)
        print(f"[lacc] offset={offset} → {added} events")
        if added == 0:
            break
        offset += PER_PAGE

    return events
