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
import subprocess
import tarfile

import brotli

LAYER_BIN = "/opt/nodejs/node_modules/@sparticuz/chromium/bin"
_CHROMIUM_PATH = "/tmp/chromium"

# Matches sparticuz/chromium default args exactly (no --disable-gpu, no --no-zygote).
# https://github.com/Sparticuz/chromium
LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--allow-running-insecure-content",
    "--autoplay-policy=user-gesture-required",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process",
    "--disable-features=Translate,BackForwardCache,AvoidUnnecessaryBeforeUnloadCheckPost",
    "--disable-print-preview",
    "--disable-site-isolation-trials",
    "--disable-speech-api",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-client-side-phishing-detection",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-sync",
    "--force-color-profile=srgb",
    "--metrics-recording-only",
    "--no-first-run",
    "--password-store=basic",
    "--use-mock-keychain",
    "--export-tagged-pdf",
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
        with open(al2023, "rb") as f:
            tar_bytes = brotli.decompress(f.read())
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
            members = tar.getnames()
            print(f"[playwright] al2023.tar.br contents ({len(members)} files): {members[:10]}")
            tar.extractall("/tmp")
        print(f"[playwright] /tmp contents after AL2023 extract: {os.listdir('/tmp')}")
    else:
        print(f"[playwright] WARNING: {al2023} not found")

    # 3. Extract SwiftShader (software GPU fallback)
    swiftshader = f"{LAYER_BIN}/swiftshader.tar.br"
    if os.path.isfile(swiftshader):
        print(f"[playwright] Extracting SwiftShader from {swiftshader}")
        _extract_tar_br(swiftshader, "/tmp")
        swiftshader_contents = []
        for root, _, files in os.walk("/tmp"):
            for f in files:
                swiftshader_contents.append(os.path.join(root, f))
        print(f"[playwright] /tmp after SwiftShader: {swiftshader_contents[:20]}")
    else:
        print(f"[playwright] WARNING: {swiftshader} not found")

    # 3a. Point Vulkan loader at the SwiftShader ICD and fix library path if needed.
    icd_path = "/tmp/vk_swiftshader_icd.json"
    if os.path.isfile(icd_path):
        import json as _json
        with open(icd_path) as f:
            icd = _json.load(f)
        print(f"[playwright] vk_swiftshader_icd.json: {icd}")
        # The ICD may reference a path that no longer exists after extraction;
        # rewrite it to point at the extracted library in /tmp.
        lib_path = icd.get("ICD", {}).get("library_path", "")
        if lib_path and not os.path.isfile(lib_path):
            icd["ICD"]["library_path"] = "/tmp/libvk_swiftshader.so"
            with open(icd_path, "w") as f:
                _json.dump(icd, f)
            print(f"[playwright] Patched ICD library_path → /tmp/libvk_swiftshader.so")
        os.environ["VK_ICD_FILENAMES"] = icd_path
        print(f"[playwright] VK_ICD_FILENAMES={icd_path}")
    else:
        print(f"[playwright] WARNING: {icd_path} not found")

    # 4. Extract fonts (needed for renderer stability)
    fonts = f"{LAYER_BIN}/fonts.tar.br"
    if os.path.isfile(fonts):
        print(f"[playwright] Extracting fonts from {fonts}")
        _extract_tar_br(fonts, "/tmp")
    else:
        print(f"[playwright] WARNING: {fonts} not found")

    # 5. Set environment variables Chromium needs
    os.environ.setdefault("HOME", "/tmp")
    os.environ.setdefault("FONTCONFIG_PATH", "/tmp/aws")

    # 6. Set LD_LIBRARY_PATH so Chromium can find the extracted shared libraries.
    lib_dirs = [d for d in ("/tmp", "/tmp/lib") if os.path.isdir(d)]
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = ":".join(lib_dirs) + (":" + existing if existing else "")
    print(f"[playwright] LD_LIBRARY_PATH={os.environ['LD_LIBRARY_PATH']}")

    # 7. Smoke-test the binary so we can see its crash output before Playwright tries.
    try:
        result = subprocess.run(
            [_CHROMIUM_PATH, "--version", "--no-sandbox"],
            capture_output=True, text=True, timeout=10, env=os.environ,
        )
        print(f"[playwright] Chromium --version: rc={result.returncode} stdout={result.stdout.strip()!r} stderr={result.stderr[:400]!r}")
    except Exception as e:
        print(f"[playwright] Chromium --version failed: {e}")

    print(f"[playwright] Chromium ready at {_CHROMIUM_PATH}")
    return _CHROMIUM_PATH
