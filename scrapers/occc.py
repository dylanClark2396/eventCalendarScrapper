"""
Scraper for Orange County Convention Center event calendar.
https://events.occc.net/
Uses the public RSS feed.
"""

import re
import xml.etree.ElementTree as ET

import requests

CALENDAR_ID = "occc"
CALENDAR_NAME = "Orange County Convention Center"
RSS_URL = "https://events.occc.net/event/rss/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# Matches "03/18/2026 to 03/22/2026" in description CDATA
DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})")


def fetch_events() -> list[dict]:
    response = requests.get(RSS_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    channel = root.find("channel")
    if channel is None:
        return []

    events = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "")

        match = DATE_RE.search(description)
        if match:
            start, end = match.group(1), match.group(2)
            date_str = start if start == end else f"{start} – {end}"
        else:
            date_str = ""

        events.append({
            "title": title,
            "date": date_str,
            "description": "",
            "link": link,
        })

    return events
