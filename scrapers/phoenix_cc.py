"""
Scraper for Phoenix Convention Center event calendar.
https://www.phoenixconventioncenter.com/events
Uses the Ungerboeck API.
"""

from datetime import datetime, timezone

import requests

CALENDAR_ID = "phoenix_cc"
CALENDAR_NAME = "Phoenix Convention Center"
API_URL = "https://phoenixcc-web.ungerboeck.com/Digital_Services/api/events/getall"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def parse_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
        return iso_str


def fetch_events() -> list[dict]:
    start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    response = requests.get(
        API_URL,
        params={"orgcode": "01", "start": start},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    events = []
    for item in data:
        title = item.get("title", "").strip()
        if not title:
            continue

        start_str = parse_date(item.get("start", ""))
        end_str = parse_date(item.get("end", ""))
        date_str = start_str if start_str == end_str else f"{start_str} – {end_str}"

        events.append({
            "id": str(item.get("id", "")),
            "title": title,
            "date": date_str,
            "description": item.get("event_notes_description", ""),
            "link": item.get("event_url", ""),
        })

    return events
