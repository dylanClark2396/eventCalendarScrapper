"""
Shared Playwright browser launch helpers for headless scrapers.
Chromium binary is provided by the sparticuz/chromium Lambda Layer.
"""

import glob
import os

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


def find_chromium() -> str:
    """Locate the Chromium binary from the Lambda Layer."""
    # Env var override takes precedence
    if os.environ.get("CHROMIUM_PATH"):
        return os.environ["CHROMIUM_PATH"]

    # Search /opt for any executable named 'chromium' or 'chrome'
    for pattern in ("/opt/**/chromium", "/opt/**/chrome", "/opt/chromium", "/opt/chrome"):
        matches = glob.glob(pattern, recursive=True)
        for match in matches:
            if os.path.isfile(match) and os.access(match, os.X_OK):
                print(f"[playwright] Found Chromium at: {match}")
                return match

    # Last resort default
    return "/opt/chromium"


CHROMIUM_PATH = find_chromium()
