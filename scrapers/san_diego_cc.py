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

        def get_caldate(cls):
            el = item.find("div", class_=cls)
            if not el:
                return ""
            month = el.find("div", class_="month")
            day = el.find("div", class_="day")
            m = month.find("span", class_="field-value").get_text(strip=True) if month else ""
            d = day.find("span", class_="field-value").get_text(strip=True) if day else ""
            return f"{m} {d}".strip()

        start_str = get_caldate("startmo")
        end_str = get_caldate("endmo")
        date_str = start_str if start_str == end_str else f"{start_str} – {end_str}"

        events.append({
            "title": title,
            "date": date_str,
            "description": "",
            "link": link,
        })

    return events
