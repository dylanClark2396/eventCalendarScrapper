"""
Scraper for Las Vegas convention events calendar.
https://www.vegasmeansbusiness.com/destination-calendar/
Uses the public RSS feed, filtered to convention events only.
"""

import re
import xml.etree.ElementTree as ET

import requests

CALENDAR_ID = "vegas_lvcva"
CALENDAR_NAME = "Las Vegas Conventions"
RSS_URL = "https://www.vegasmeansbusiness.com/event/rss/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# Matches "03/19/2026 to 03/21/2026" in description CDATA
DATE_RANGE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})")
# Matches "Starting 01/01/2025"
DATE_STARTING_RE = re.compile(r"Starting\s+(\d{2}/\d{2}/\d{4})")


def fetch_events() -> list[dict]:
    response = requests.get(RSS_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    channel = root.find("channel")
    if channel is None:
        return []

    events = []
    for item in channel.findall("item"):
        # Exclude entertainment/shows — keep conventions, trade shows, conferences
        categories = [c.text.strip() for c in item.findall("category") if c.text]
        if any(cat.startswith("Shows:") for cat in categories):
            continue

        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        link = (item.findtext("link") or "").strip()
        description = item.findtext("description") or ""

        range_match = DATE_RANGE_RE.search(description)
        start_match = DATE_STARTING_RE.search(description)

        if range_match:
            start, end = range_match.group(1), range_match.group(2)
            date_str = start if start == end else f"{start} – {end}"
        elif start_match:
            date_str = start_match.group(1)
        else:
            date_str = ""

        events.append({
            "title": title,
            "date": date_str,
            "description": "",
            "link": link,
        })

    return events
