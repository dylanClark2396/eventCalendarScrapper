"""
Scraper for Georgia International Convention Center event calendar.
https://www.gicc.com/events/list/
Uses WordPress Tribe Events HTML.
"""

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "gicc"
CALENDAR_NAME = "Georgia International Convention Center"
BASE_URL = "https://www.gicc.com/events/list/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

MAX_PAGES = 10


def fetch_page(url: str) -> list[dict]:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    for card in soup.find_all("div", class_="tribe-events-calendar-list__event"):
        title_el = card.find("h3", class_="tribe-events-calendar-list__event-title")
        if not title_el or not title_el.a:
            continue
        title = title_el.a.get_text(strip=True)
        link = title_el.a.get("href", "")

        date_el = card.find("div", class_="tribe-events-calendar-list__event-date-tag")
        date_str = date_el.get_text(strip=True) if date_el else ""

        desc_el = card.find("p", class_="tribe-events-calendar-list__event-description")
        description = desc_el.get_text(strip=True) if desc_el else ""

        events.append({
            "title": title,
            "date": date_str,
            "description": description,
            "link": link,
        })

    # Return next page URL if present
    next_el = soup.find("a", class_="tribe-events-c-nav__next")
    next_url = next_el.get("href") if next_el else None

    return events, next_url


def fetch_events() -> list[dict]:
    all_events = []
    url = BASE_URL

    for _ in range(MAX_PAGES):
        events, next_url = fetch_page(url)
        all_events.extend(events)
        if not next_url:
            break
        url = next_url

    return all_events
