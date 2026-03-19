"""
Shared Playwright browser launch helpers for headless scrapers.
Chromium binary is provided by the sparticuz/chromium Lambda Layer.

sparticuz/chromium v110+ ships the binary brotli-compressed as chromium.br.
This module decompresses it to /tmp/chromium on first use (cached across warm starts).
"""

import os
import stat

import brotli

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

_COMPRESSED_PATHS = [
    "/opt/chromium.br",
    "/opt/al2023/chromium.br",
]
_DECOMPRESSED_PATH = "/tmp/chromium"


def prepare_chromium() -> str:
    """
    Return a path to a ready-to-run Chromium binary.
    Decompresses the brotli-compressed layer binary on first call;
    subsequent calls on warm Lambdas reuse /tmp/chromium.
    """
    # Env var override (e.g. for local testing)
    if os.environ.get("CHROMIUM_PATH"):
        return os.environ["CHROMIUM_PATH"]

    # Already decompressed on a warm Lambda
    if os.path.isfile(_DECOMPRESSED_PATH) and os.access(_DECOMPRESSED_PATH, os.X_OK):
        return _DECOMPRESSED_PATH

    # Decompress from layer
    for br_path in _COMPRESSED_PATHS:
        if os.path.isfile(br_path):
            print(f"[playwright] Decompressing {br_path} → {_DECOMPRESSED_PATH}")
            with open(br_path, "rb") as f:
                data = brotli.decompress(f.read())
            with open(_DECOMPRESSED_PATH, "wb") as f:
                f.write(data)
            os.chmod(_DECOMPRESSED_PATH, os.stat(_DECOMPRESSED_PATH).st_mode | stat.S_IEXEC)
            return _DECOMPRESSED_PATH

    # Fallback: uncompressed binary already in layer
    for path in ("/opt/chromium", "/opt/chrome"):
        if os.path.isfile(path):
            print(f"[playwright] Using uncompressed binary at {path}")
            return path

    # Log /opt contents to CloudWatch to help debug missing binary
    print("[playwright] WARNING: Chromium binary not found. /opt contents:")
    for root, dirs, files in os.walk("/opt"):
        for name in files:
            print(f"  {os.path.join(root, name)}")
    return _DECOMPRESSED_PATH  # will fail, but error will be clear


CHROMIUM_PATH = prepare_chromium()
