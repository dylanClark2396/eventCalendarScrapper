"""
Scraper for Kay Bailey Hutchison Convention Center event calendar.
https://www.dallasconventioncenter.com/events
"""

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "dallas_cc"
CALENDAR_NAME = "Kay Bailey Hutchison Convention Center"
CALENDAR_URL = "https://www.dallasconventioncenter.com/events"

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

    # Each event has an h3 containing an anchor to its detail page
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=lambda h: h and "/events/detail/" in h)
        if not a:
            continue
        title = a.get_text(strip=True)
        link = a.get("href", "")
        if not title or title in seen:
            continue
        seen.add(title)

        # Date is in the <p> immediately before the <h3>
        date_str = ""
        prev = h3.find_previous_sibling("p")
        if prev:
            date_str = prev.get_text(strip=True)

        # Description is in the <h4> immediately after the <h3>
        description = ""
        nxt = h3.find_next_sibling("h4")
        if nxt:
            description = nxt.get_text(strip=True)

        events.append({
            "title": title,
            "date": date_str,
            "description": description,
            "link": link,
        })

    return events
