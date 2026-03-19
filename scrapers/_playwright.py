"""
Shared Playwright browser launch helpers for headless scrapers.
Chromium binary is provided by the sparticuz/chromium Lambda Layer at /opt/chromium.
"""

import os

CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH", "/opt/chromium")

LAUNCH_ARGS = [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--single-process",
    "--no-zygote",
    "--disable-setuid-sandbox",
    "--disable-extensions",
]
