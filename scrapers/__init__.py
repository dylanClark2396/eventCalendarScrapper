from scrapers import (
    dallas_cc,
    gicc,
    gwcca,
    javits,
    lacc,
    miami_beach_cc,
    nashville_mcc,
    occc,
    phoenix_cc,
    san_diego_cc,
    signature_boston,
    vegas_lvcva,
)

# Register every calendar scraper here.
# Each module must expose:
#   CALENDAR_ID   str  — used as the S3 folder name and log prefix
#   CALENDAR_NAME str  — human-readable display name
#   fetch_events() -> list[dict]  — returns a list of event dicts with keys:
#                                   title, date, description, link
ALL = [
    dallas_cc,
    gicc,
    javits,
    lacc,
    miami_beach_cc,
    nashville_mcc,
    phoenix_cc,
    san_diego_cc,
    signature_boston,
    # gwcca, occc, vegas_lvcva disabled — Chromium/Playwright does not work reliably on Lambda
]
