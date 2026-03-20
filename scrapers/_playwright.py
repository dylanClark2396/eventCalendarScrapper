"""
Shared Playwright browser launch helpers for headless scrapers.
Chromium binary is provided by the sparticuz/chromium Lambda Layer.

Layer file structure (all under /opt/nodejs/node_modules/@sparticuz/chromium/bin/):
  chromium.br       — the Chromium binary, brotli-compressed (decompress → /tmp/chromium)
  al2023.tar.br     — AL2023 shared libraries, tar+brotli (extract → /tmp/)
  swiftshader.tar.br — SwiftShader GPU fallback libs, tar+brotli (extract → /tmp/)
  fonts.tar.br      — fonts, tar+brotli (extract → /tmp/)

Reference: https://github.com/Sparticuz/chromium
"""

import io
import os
import stat
import tarfile

import brotli

LAYER_BIN = "/opt/nodejs/node_modules/@sparticuz/chromium/bin"
_CHROMIUM_PATH = "/tmp/chromium"

LAUNCH_ARGS = [
    "--headless=new",
    "--no-sandbox",
    "--no-zygote",
    "--single-process",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-sync",
    "--no-first-run",
    "--use-gl=swiftshader",
]


def _extract_tar_br(path: str, dest: str) -> None:
    """Decompress a tar+brotli archive and extract to dest."""
    with open(path, "rb") as f:
        tar_bytes = brotli.decompress(f.read())
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        tar.extractall(dest)


def prepare_chromium() -> str:
    """Return a path to a ready-to-run Chromium binary, extracting from the layer if needed."""
    if os.environ.get("CHROMIUM_PATH"):
        return os.environ["CHROMIUM_PATH"]

    # Warm Lambda — already extracted
    if os.path.isfile(_CHROMIUM_PATH) and os.access(_CHROMIUM_PATH, os.X_OK):
        return _CHROMIUM_PATH

    # 1. Extract the Chromium binary: chromium.br is plain brotli (not a tar)
    br_path = f"{LAYER_BIN}/chromium.br"
    if not os.path.isfile(br_path):
        raise RuntimeError(f"Chromium binary not found at {br_path}")

    print(f"[playwright] Decompressing {br_path} → {_CHROMIUM_PATH}")
    with open(br_path, "rb") as f:
        data = brotli.decompress(f.read())
    with open(_CHROMIUM_PATH, "wb") as f:
        f.write(data)
    os.chmod(_CHROMIUM_PATH, 0o755)

    # 2. Extract AL2023 shared libraries (needed on python3.12 / AL2023 runtime)
    al2023 = f"{LAYER_BIN}/al2023.tar.br"
    if os.path.isfile(al2023):
        print(f"[playwright] Extracting AL2023 libs from {al2023}")
        _extract_tar_br(al2023, "/tmp")

    # 3. Extract SwiftShader (software GPU fallback)
    swiftshader = f"{LAYER_BIN}/swiftshader.tar.br"
    if os.path.isfile(swiftshader):
        print(f"[playwright] Extracting SwiftShader from {swiftshader}")
        _extract_tar_br(swiftshader, "/tmp")

    # 4. Set LD_LIBRARY_PATH so Chromium can find the extracted shared libraries.
    #    Sparticuz libs may land in /tmp directly or in /tmp/lib depending on tar structure.
    lib_dirs = [d for d in ("/tmp", "/tmp/lib") if os.path.isdir(d)]
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = ":".join(lib_dirs) + (":" + existing if existing else "")
    print(f"[playwright] LD_LIBRARY_PATH={os.environ['LD_LIBRARY_PATH']}")

    print(f"[playwright] Chromium ready at {_CHROMIUM_PATH}")
    return _CHROMIUM_PATH
