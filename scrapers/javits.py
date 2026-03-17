"""
Scraper for the Javits Center event calendar.
https://www.javitscenter.com/calendar/
"""

import requests
from bs4 import BeautifulSoup

CALENDAR_ID = "javits"
CALENDAR_NAME = "Javits Center"
CALENDAR_URL = "https://www.javitscenter.com/calendar/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

MONTH_HEADERS = {
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
}


def fetch_events() -> list[dict]:
    response = requests.get(CALENDAR_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events: list[dict] = []

    def clean_link(href: str) -> str:
        href = href.strip()
        return href if href.startswith("http") else ""

    def extract_list_event(article) -> dict | None:
        """Parse an article.lv-container (list view) element."""
        summary = article.find("summary", class_="lv-main")
        if not summary:
            return None
        h3 = summary.find("h3")
        if not h3:
            return None
        title = h3.get_text(separator=" ", strip=True)
        title = " ".join(w for w in title.split() if len(w) > 1 or w.isalpha())
        if not title:
            return None

        date_tag = summary.find("strong")
        date_str = date_tag.get_text(strip=True) if date_tag else ""

        lv_more = article.find("div", class_="lv-more")
        description = ""
        link = ""
        if lv_more:
            a_tag = lv_more.find("a", class_="calendar-button", href=True)
            link = clean_link(a_tag["href"]) if a_tag else ""
            if a_tag:
                a_tag.extract()
            description = lv_more.get_text(separator=" ", strip=True)

        return {"title": title, "date": date_str, "description": description, "link": link}

    def extract_calendar_event(container) -> dict | None:
        """Parse a div.container (calendar view) element."""
        h3 = container.find("h3")
        if not h3:
            return None
        title = h3.get_text(strip=True)
        if not title or any(m in title for m in MONTH_HEADERS):
            return None

        date_tag = container.find("p", class_="modal-date")
        date_str = date_tag.get_text(strip=True) if date_tag else ""

        a_tag = container.find("a", class_="button", href=True)
        link = clean_link(a_tag["href"]) if a_tag else ""

        desc_parts = []
        for p in container.find_all("p"):
            if p.get("class") == ["modal-date"]:
                continue
            text = p.get_text(separator=" ", strip=True)
            if text and text != date_str:
                desc_parts.append(text)
        description = " ".join(desc_parts)

        return {"title": title, "date": date_str, "description": description, "link": link}

    # List view first (richest data)
    for article in soup.find_all("article", class_="lv-container"):
        event = extract_list_event(article)
        if event:
            events.append(event)

    # Calendar view — supplement with any events not in the list view
    list_titles = {e["title"] for e in events}
    for container in soup.find_all("div", class_="container"):
        if container.find_parent("article", class_="lv-container"):
            continue
        event = extract_calendar_event(container)
        if event and event["title"] not in list_titles:
            events.append(event)
            list_titles.add(event["title"])

    # Deduplicate by (title, date)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for event in events:
        key = (event["title"], event["date"])
        if key not in seen:
            seen.add(key)
            unique.append(event)

    return unique
