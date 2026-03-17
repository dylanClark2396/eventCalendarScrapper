from scrapers import javits

# Register every calendar scraper here.
# Each module must expose:
#   CALENDAR_ID   str  — used as the S3 folder name and log prefix
#   CALENDAR_NAME str  — human-readable display name
#   fetch_events() -> list[dict]  — returns a list of event dicts with keys:
#                                   title, date, description, link
ALL = [javits]
