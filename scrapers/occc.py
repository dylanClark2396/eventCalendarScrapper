"""
Scraper for Orange County Convention Center event calendar.
https://events.occc.net/
Vue.js + Ungerboeck rendered — uses Playwright to intercept the REST API response.
"""

import json

from playwright.sync_api import sync_playwright

from scrapers._playwright import LAUNCH_ARGS, prepare_chromium

CALENDAR_ID = "occc"
CALENDAR_NAME = "Orange County Convention Center"
CALENDAR_URL = "https://events.occc.net/"
API_PATH = "plugins_events_events_by_date/find"


def fetch_events() -> list[dict]:
    api_payloads = []

    chromium_path = prepare_chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path, headless=False, args=LAUNCH_ARGS)
        page = browser.new_page()

        def handle_response(response):
            if API_PATH in response.url:
                try:
                    api_payloads.append(response.json())
                except Exception:
                    pass

        # Block heavy resources — we only need the JS API calls to fire, not full rendering
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,mp4,mp3}",
            lambda route: route.abort(),
        )
        page.route("**/*.css", lambda route: route.abort())

        page.on("response", handle_response)
        page.goto(CALENDAR_URL, wait_until="load", timeout=60000)
        # Wait for Ungerboeck API calls to complete after initial load
        page.wait_for_timeout(10000)
        browser.close()

    events = []
    seen = set()

    for payload in api_payloads:
        items = payload if isinstance(payload, list) else payload.get("items", [])
        for item in items:
            title = (item.get("Description") or item.get("EventName") or item.get("title") or "").strip()
            if not title:
                continue

            start = item.get("StartDate") or item.get("start_date") or item.get("start") or ""
            end = item.get("EndDate") or item.get("end_date") or item.get("end") or ""
            if end and end != start:
                date_str = f"{start} – {end}"
            else:
                date_str = start

            link = item.get("WebAddress") or item.get("url") or item.get("link") or ""
            if link and not link.startswith("http"):
                link = f"https://events.occc.net{link}"

            key = (title, date_str)
            if key not in seen:
                seen.add(key)
                events.append({
                    "title": title,
                    "date": date_str,
                    "description": "",
                    "link": link,
                })

    return events
