"""
Scraper for Georgia World Congress Center event calendar.
https://www.gwcca.org/event-calendar
Vue.js SSR — uses Playwright to load the page (site blocks direct fetches),
then extracts events from:
  1. JSON-LD <script type="application/ld+json"> Event schemas (SSR)
  2. Intercepted API responses (if Vue makes XHR/fetch calls)
  3. SSR HTML structure (fallback)
"""

import json
import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scrapers._playwright import LAUNCH_ARGS, prepare_chromium

CALENDAR_ID = "gwcca"
CALENDAR_NAME = "Georgia World Congress Center"
CALENDAR_URL = "https://www.gwcca.org/event-calendar"

_DATE_RE = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z.]*'
    r'\s+\d{1,2}(?:\s*[-–]\s*(?:\w+\s+)?\d{1,2})?,?\s*\d{4}',
    re.IGNORECASE,
)


def _parse_html(html: str) -> list[dict]:
    """Extract events from SSR HTML via JSON-LD or DOM heuristics."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    # Strategy 1: JSON-LD Event schemas
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") not in ("Event", "BusinessEvent", "SocialEvent"):
                continue
            title = (item.get("name") or "").strip()
            if not title:
                continue
            start = item.get("startDate", "")
            end = item.get("endDate", "")
            date_str = f"{start} – {end}" if end and end != start else start
            link = item.get("url", "")
            key = (title, date_str)
            if key not in seen:
                seen.add(key)
                events.append({"title": title, "date": date_str, "description": "", "link": link})

    if events:
        print(f"[gwcca] Found {len(events)} events via JSON-LD")
        return events

    # Strategy 2: Embedded window state (Vue SSR often serialises state into a script tag)
    for script in soup.find_all("script"):
        text = script.string or ""
        for pattern in (r'window\.__(?:INITIAL_STATE|NUXT|DATA)__\s*=\s*(\{.*)', r'"events"\s*:\s*(\[.*?)(?=\s*[,}])'):
            m = re.search(pattern, text, re.DOTALL)
            if m:
                try:
                    payload = json.loads(m.group(1).rstrip(";"))
                    items = payload if isinstance(payload, list) else payload.get("events") or payload.get("items") or []
                    for item in items:
                        title = (item.get("title") or item.get("name") or "").strip()
                        if not title:
                            continue
                        start = item.get("startDate") or item.get("start_date") or item.get("start") or ""
                        end = item.get("endDate") or item.get("end_date") or item.get("end") or ""
                        date_str = f"{start} – {end}" if end and end != start else start
                        link = item.get("url") or item.get("link") or ""
                        if link and link.startswith("/"):
                            link = f"https://www.gwcca.org{link}"
                        key = (title, date_str)
                        if key not in seen:
                            seen.add(key)
                            events.append({"title": title, "date": date_str, "description": "", "link": link})
                    if events:
                        print(f"[gwcca] Found {len(events)} events via embedded state")
                        return events
                except Exception:
                    pass

    # Strategy 3: DOM heuristics — elements with "event" in class name containing a title + date
    for el in soup.find_all(class_=re.compile(r'event', re.I)):
        heading = el.find(re.compile(r'^h[1-6]$'))
        if not heading:
            continue
        title = heading.get_text(strip=True)
        if not title:
            continue
        date_str = ""
        for cls in ("event-date", "date", "dates", "event-dates", "event-time"):
            date_el = el.find(class_=cls)
            if date_el:
                date_str = date_el.get_text(strip=True)
                break
        if not date_str:
            m = _DATE_RE.search(el.get_text(separator=" "))
            date_str = m.group(0).strip() if m else ""
        a = heading.find("a") or el.find("a")
        link = a.get("href", "") if a else ""
        if link and link.startswith("/"):
            link = f"https://www.gwcca.org{link}"
        key = (title, date_str)
        if key not in seen:
            seen.add(key)
            events.append({"title": title, "date": date_str, "description": "", "link": link})

    if events:
        print(f"[gwcca] Found {len(events)} events via DOM heuristics")
    else:
        print("[gwcca] No events found in HTML — dumping head for debugging:")
        print(html[:2000])

    return events


def fetch_events() -> list[dict]:
    api_payloads = []
    page_html = ""

    chromium_path = prepare_chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path, headless=False, args=LAUNCH_ARGS)
        page = browser.new_page()

        # Block heavy assets to reduce renderer crash risk
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,mp4,mp3}",
            lambda route: route.abort(),
        )
        page.route("**/*.css", lambda route: route.abort())

        def handle_response(response):
            try:
                if "json" in response.headers.get("content-type", ""):
                    data = response.json()
                    if data:
                        print(f"[gwcca] API response: {response.url[:120]} → keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}[{len(data) if isinstance(data, list) else ''}]")
                        api_payloads.append((response.url, data))
            except Exception:
                pass

        page.on("response", handle_response)
        try:
            page.goto(CALENDAR_URL, wait_until="domcontentloaded", timeout=60000)
            # Grab the SSR HTML immediately before Vue hydration can crash the renderer
            page_html = page.content()
            print(f"[gwcca] Got page HTML ({len(page_html)} bytes), waiting for API calls...")
            page.wait_for_timeout(8000)
        except Exception as e:
            print(f"[gwcca] page error (may be post-SSR crash): {e}")
            if not page_html:
                try:
                    page_html = page.content()
                except Exception:
                    pass
        browser.close()

    # Try API payloads first (more structured)
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
                events.append({"title": title, "date": date_str, "description": "", "link": link})

    if events:
        print(f"[gwcca] Returning {len(events)} events from API interception")
        return events

    # Fall back to HTML parsing
    if page_html:
        events = _parse_html(page_html)

    print(f"[gwcca] Returning {len(events)} events total")
    return events
