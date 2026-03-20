"""
Scraper for Georgia World Congress Center event calendar.
https://www.gwcca.org/event-calendar
Vue.js rendered — uses Playwright with headless Chromium.
"""

from playwright.sync_api import sync_playwright

from scrapers._playwright import LAUNCH_ARGS, prepare_chromium

CALENDAR_ID = "gwcca"
CALENDAR_NAME = "Georgia World Congress Center"
CALENDAR_URL = "https://www.gwcca.org/event-calendar"


def fetch_events() -> list[dict]:
    events = []
    seen = set()

    chromium_path = prepare_chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path, args=LAUNCH_ARGS)
        page = browser.new_page()
        page.goto(CALENDAR_URL, wait_until="load", timeout=60000)
        # Give Vue time to render after initial load
        page.wait_for_timeout(8000)

        # Wait for event cards to appear after Vue renders
        page.wait_for_selector(".event-listing, .event-card, .event-item, article", timeout=20000)

        cards = (
            page.query_selector_all(".event-listing")
            or page.query_selector_all(".event-card")
            or page.query_selector_all(".event-item")
            or page.query_selector_all("article")
        )

        for card in cards:
            # Title — try common heading selectors
            title_el = (
                card.query_selector("h3")
                or card.query_selector("h2")
                or card.query_selector("h4")
                or card.query_selector(".event-title")
                or card.query_selector(".event-name")
            )
            if not title_el:
                continue
            title = title_el.inner_text().strip()
            if not title:
                continue

            # Link
            link_el = card.query_selector("a")
            href = link_el.get_attribute("href") if link_el else ""
            if href and href.startswith("/"):
                href = f"https://www.gwcca.org{href}"

            # Date
            date_el = (
                card.query_selector(".event-date")
                or card.query_selector(".date")
                or card.query_selector("time")
                or card.query_selector(".event-dates")
            )
            date_str = date_el.inner_text().strip() if date_el else ""

            key = (title, date_str)
            if key not in seen:
                seen.add(key)
                events.append({
                    "title": title,
                    "date": date_str,
                    "description": "",
                    "link": href,
                })

        browser.close()

    return events
