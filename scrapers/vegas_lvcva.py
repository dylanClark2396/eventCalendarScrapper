"""
Scraper for Las Vegas convention events calendar.
https://www.vegasmeansbusiness.com/destination-calendar/
Simpleview JS-rendered — uses Playwright to intercept the API response.
Direct API calls time out from Lambda (AWS IPs blocked); Playwright is required.
"""

from playwright.sync_api import sync_playwright

from scrapers._playwright import LAUNCH_ARGS, prepare_chromium

CALENDAR_ID = "vegas_lvcva"
CALENDAR_NAME = "Las Vegas Conventions"
CALENDAR_URL = "https://www.vegasmeansbusiness.com/destination-calendar/"


def fetch_events() -> list[dict]:
    api_payloads = []

    chromium_path = prepare_chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path, headless=False, args=LAUNCH_ARGS)
        page = browser.new_page()

        def handle_response(response):
            # Simpleview loads calendar data via its svapi or internal widget API
            if "svapi" in response.url or "calendar" in response.url or "convention" in response.url.lower():
                try:
                    data = response.json()
                    if data and isinstance(data, (dict, list)):
                        print(f"[vegas_lvcva] Intercepted: {response.url[:120]}")
                        api_payloads.append((response.url, data))
                except Exception:
                    pass

        page.on("response", handle_response)
        try:
            page.goto(CALENDAR_URL, wait_until="load", timeout=60000)
            # Initial load — wait for calendar widget to render
            page.wait_for_timeout(8000)
            # Scroll down several times to trigger lazy-loaded pagination
            for _ in range(5):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[vegas_lvcva] page error (keeping any captured payloads): {e}")
        browser.close()

    events = []
    seen = set()

    for url, payload in api_payloads:
        # Simpleview responses may be nested under various keys
        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            for key in ("docs", "list", "results", "items", "data", "events", "records"):
                if isinstance(payload.get(key), list):
                    items = payload[key]
                    break

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
