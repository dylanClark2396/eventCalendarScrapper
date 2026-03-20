"""
Scraper for Las Vegas convention events calendar.
https://www.vegasmeansbusiness.com/destination-calendar/
Simpleview REST API — direct requests, no Playwright needed.
Token is static and does not require auth headers.
"""

import datetime

import requests

CALENDAR_ID = "vegas_lvcva"
CALENDAR_NAME = "Las Vegas Conventions"
CALENDAR_URL = "https://www.vegasmeansbusiness.com/destination-calendar/"

_API_URL = "https://www.vegasmeansbusiness.com/includes/rest_v2/plugins_events_events_by_date/find/"
_TOKEN = "675d5ae75a24f8cefebba2f84d334181"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": CALENDAR_URL,
}


def fetch_events() -> list[dict]:
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=365)

    params = {
        "token": _TOKEN,
        "calendarid": "conventions",
        "startdate": today.strftime("%Y-%m-%d"),
        "enddate": end_date.strftime("%Y-%m-%d"),
        "limit": 200,
        "skip": 0,
    }

    response = requests.get(_API_URL, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    print(f"[vegas_lvcva] API response keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")

    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("docs", "list", "results", "items", "data", "events", "records"):
            if isinstance(data.get(key), list):
                items = data[key]
                print(f"[vegas_lvcva] Found {len(items)} items under key '{key}'")
                break

    events = []
    seen = set()

    for item in items:
        title = (
            item.get("title") or item.get("name") or item.get("EventName")
            or item.get("event_name") or ""
        ).strip()
        if not title:
            continue

        start = (item.get("startDate") or item.get("start_date")
                 or item.get("StartDate") or item.get("start") or "")
        end = (item.get("endDate") or item.get("end_date")
               or item.get("EndDate") or item.get("end") or "")
        if end and end != start:
            date_str = f"{start} – {end}"
        else:
            date_str = start

        link = item.get("url") or item.get("link") or item.get("WebAddress") or ""
        if link and link.startswith("/"):
            link = f"https://www.vegasmeansbusiness.com{link}"

        key = (title, date_str)
        if key not in seen:
            seen.add(key)
            events.append({
                "title": title,
                "date": date_str,
                "description": "",
                "link": link,
            })

    print(f"[vegas_lvcva] Returning {len(events)} events")
    return events
