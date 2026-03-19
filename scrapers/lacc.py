"""
Scraper for Los Angeles Convention Center event calendar.
https://www.laconventioncenter.com/events
"""

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "lacc"
CALENDAR_NAME = "Los Angeles Convention Center"
CALENDAR_URL = "https://www.laconventioncenter.com/events"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def fetch_events() -> list[dict]:
    response = requests.get(CALENDAR_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    for card in soup.find_all("div", class_="event-item"):
        h3 = card.find("h3")
        if not h3:
            continue
        a = h3.find("a", href=lambda h: h and "/events/detail/" in h)
        if not a:
            continue
        title = a.get_text(strip=True)
        link = a.get("href", "")
        if not title or title in seen:
            continue
        seen.add(title)

        date_el = card.find("p", class_="event-date")
        date_str = date_el.get_text(strip=True) if date_el else ""

        events.append({
            "title": title,
            "date": date_str,
            "description": "",
            "link": link,
        })

    return events
