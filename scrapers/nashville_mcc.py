"""
Scraper for Music City Center event calendar.
https://nashvillemcc.com/calendar
"""

import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "nashville_mcc"
CALENDAR_NAME = "Music City Center"
CALENDAR_URL = "https://nashvillemcc.com/calendar"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def parse_date(iso_str: str) -> str:
    """Convert ISO 8601 UTC date string to a readable date string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
        return iso_str


def fetch_events() -> list[dict]:
    response = requests.get(CALENDAR_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Events are embedded as JSON inside a console.log() call in a script tag
    raw_json = None
    for script in soup.find_all("script"):
        text = script.string or ""
        match = re.search(r"console\.log\((\[.*\])\)", text, re.DOTALL)
        if match:
            raw_json = match.group(1)
            break

    if not raw_json:
        raise RuntimeError("Could not find embedded event JSON on Nashville MCC page")

    data = json.loads(raw_json)

    events = []
    for item in data:
        title = item.get("Description") or item.get("LegalName", "")
        if not title:
            continue

        start = item.get("StartDate", "")
        end = item.get("EndDate", "")
        start_str = parse_date(start) if start else ""
        end_str = parse_date(end) if end else ""
        date_str = start_str if start_str == end_str else f"{start_str} – {end_str}"

        raw_url = item.get("WebAddress", "")
        if raw_url and not raw_url.startswith("http"):
            raw_url = "https://" + raw_url

        events.append({
            "id": str(item.get("EventID", "")),
            "title": title.strip(),
            "date": date_str,
            "description": "",
            "link": raw_url,
        })

    return events
