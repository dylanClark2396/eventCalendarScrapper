"""
Scraper for Georgia World Congress Center event calendar.
https://www.gwcca.org/event-calendar
Vue.js rendered — uses Playwright to intercept the REST API response.
DOM scraping was abandoned because the renderer crashes during Vue hydration.
"""

from playwright.sync_api import sync_playwright

from scrapers._playwright import LAUNCH_ARGS, prepare_chromium

CALENDAR_ID = "gwcca"
CALENDAR_NAME = "Georgia World Congress Center"
CALENDAR_URL = "https://www.gwcca.org/event-calendar"


def fetch_events() -> list[dict]:
    api_payloads = []

    chromium_path = prepare_chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path, headless=False, args=LAUNCH_ARGS)
        page = browser.new_page()

        # Block heavy assets so the renderer doesn't crash processing them
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,mp4,mp3}",
            lambda route: route.abort(),
        )
        page.route("**/*.css", lambda route: route.abort())

        def handle_response(response):
            # Log all JSON responses to discover which API carries event data
            try:
                if "json" in response.headers.get("content-type", ""):
                    data = response.json()
                    if data:
                        print(f"[gwcca] API response: {response.url[:120]} → keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}[{len(data) if isinstance(data, list) else ''}]")
                        api_payloads.append((response.url, data))
            except Exception:
                pass

        page.on("response", handle_response)
        page.goto(CALENDAR_URL, wait_until="domcontentloaded", timeout=60000)
        # Wait for Vue to make its API calls — bail out before full render crash
        page.wait_for_timeout(8000)
        browser.close()

    events = []
    seen = set()

    for url, payload in api_payloads:
        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            for key in ("events", "items", "data", "list", "results", "records"):
                if isinstance(payload.get(key), list):
                    items = payload[key]
                    break

        for item in items:
            title = (
                item.get("title") or item.get("name") or item.get("Description")
                or item.get("EventName") or ""
            ).strip()
            if not title:
                continue

            start = (item.get("startDate") or item.get("start_date")
                     or item.get("StartDate") or item.get("start") or "")
            end = (item.get("endDate") or item.get("end_date")
                   or item.get("EndDate") or item.get("end") or "")
            date_str = f"{start} – {end}" if end and end != start else start

            link = item.get("url") or item.get("link") or item.get("WebAddress") or ""
            if link and link.startswith("/"):
                link = f"https://www.gwcca.org{link}"

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
