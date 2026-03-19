"""
Scraper for San Diego Convention Center event calendar.
https://www.visitsandiego.com/calendar
"""

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "san_diego_cc"
CALENDAR_NAME = "San Diego Convention Center"
CALENDAR_URL = "https://www.visitsandiego.com/calendar"
BASE_URL = "https://www.visitsandiego.com"

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

    calendar = soup.find("div", class_="calendar")
    if not calendar:
        return events

    for item in calendar.find_all("div", class_="item"):
        a = item.find("a", href=lambda h: h and h.startswith("/calendar/"))
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        link = BASE_URL + href if href.startswith("/") else href

        details = item.find("div", class_="event-details")
        date_str = ""
        if details:
            date_spans = details.find_all("span", class_="date")
            if len(date_spans) == 1:
                date_str = date_spans[0].get_text(strip=True)
            elif len(date_spans) >= 2:
                start = date_spans[0].get_text(strip=True)
                end = date_spans[1].get_text(strip=True)
                date_str = start if start == end else f"{start} – {end}"

        events.append({
            "title": title,
            "date": date_str,
            "description": "",
            "link": link,
        })

    return events
