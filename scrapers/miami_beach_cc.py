"""
Scraper for Miami Beach Convention Center event calendar.
https://www.miamibeachconvention.com/events
Uses cloudscraper to bypass Cloudflare protection.
"""

import cloudscraper
from bs4 import BeautifulSoup

CALENDAR_ID = "miami_beach_cc"
CALENDAR_NAME = "Miami Beach Convention Center"
BASE_URL = "https://www.miamibeachconvention.com/events"


def fetch_events() -> list[dict]:
    scraper = cloudscraper.create_scraper()
    events = []
    seen = set()
    url = BASE_URL

    while url:
        response = scraper.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for article in soup.find_all("article", class_="node--event--teaser"):
            title_el = article.find("div", class_="field--name-field-display-title")
            if not title_el:
                continue
            a = title_el.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue

            href = a.get("href", "")
            link = f"https://www.miamibeachconvention.com{href}" if href.startswith("/") else href

            start_el = article.find("div", class_="start-date")
            start_date = ""
            if start_el:
                span = start_el.find("span", class_="date")
                start_date = span.get_text(strip=True) if span else ""

            end_el = article.find("div", class_="end-date")
            end_date = ""
            if end_el:
                span = end_el.find("span", class_="date")
                end_date = span.get_text(strip=True) if span else ""

            if end_date and end_date != start_date:
                date_str = f"{start_date} – {end_date}"
            else:
                date_str = start_date

            desc_el = article.find("div", class_="field--name-body")
            description = ""
            if desc_el:
                p = desc_el.find("p")
                description = p.get_text(strip=True) if p else ""

            key = (title, date_str)
            if key not in seen:
                seen.add(key)
                events.append({
                    "title": title,
                    "date": date_str,
                    "description": description,
                    "link": link,
                })

        next_el = soup.find("li", class_="pager__item--next")
        if next_el:
            next_a = next_el.find("a")
            if next_a and next_a.get("href"):
                href = next_a["href"]
                url = f"https://www.miamibeachconvention.com{href}" if href.startswith("/") else href
            else:
                url = None
        else:
            url = None

    return events
