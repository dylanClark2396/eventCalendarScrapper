#!/usr/bin/env python3
"""
Event Calendar Scraper — local CLI
Runs all registered scrapers and compares against local snapshots.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import scrapers

# Fix Windows console Unicode issues
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SNAPSHOT_DIR = Path("snapshots")


def snapshot_path(calendar_id: str) -> Path:
    return SNAPSHOT_DIR / calendar_id / "events_snapshot.json"


def load_snapshot(calendar_id: str) -> dict:
    path = snapshot_path(calendar_id)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(calendar_id: str, events: list[dict]) -> None:
    path = snapshot_path(calendar_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"scraped_at": datetime.now().isoformat(), "events": events}
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[{calendar_id}] Snapshot saved to {path} ({len(events)} events)")


def find_new_events(previous: list[dict], current: list[dict]) -> list[dict]:
    prev_keys = {(e["title"], e["date"]) for e in previous}
    return [e for e in current if (e["title"], e["date"]) not in prev_keys]


def print_events(events: list[dict], label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {label} ({len(events)})")
    print(f"{'='*60}")
    for e in events:
        print(f"  Title : {e['title']}")
        if e["date"]:
            print(f"  Dates : {e['date']}")
        if e["description"]:
            snippet = e["description"][:120]
            print(f"  Info  : {snippet}{'...' if len(e['description']) > 120 else ''}")
        if e["link"]:
            print(f"  Link  : {e['link']}")
        print()


def run_scraper(scraper) -> None:
    cid = scraper.CALENDAR_ID
    name = scraper.CALENDAR_NAME

    print(f"\n[{cid}] Scraping {name} ...")

    try:
        current_events = scraper.fetch_events()
    except Exception as e:
        print(f"[{cid}] ERROR: {e}", file=sys.stderr)
        return

    print(f"[{cid}] Found {len(current_events)} events.")

    snapshot = load_snapshot(cid)
    previous_events: list[dict] = snapshot.get("events", []) if isinstance(snapshot, dict) else []
    previous_scraped_at: str = snapshot.get("scraped_at", "unknown")

    if not previous_events:
        print(f"[{cid}] No previous snapshot — saving as baseline.")
        save_snapshot(cid, current_events)
        print_events(current_events, f"{name} — All Events (first run)")
        return

    print(f"[{cid}] Previous snapshot: {len(previous_events)} events (scraped at {previous_scraped_at})")

    new_events = find_new_events(previous_events, current_events)
    removed_events = find_new_events(current_events, previous_events)

    if new_events:
        print_events(new_events, f"{name} — NEW Events")
    else:
        print(f"[{cid}] No new events since last scrape.")

    if removed_events:
        print_events(removed_events, f"{name} — Events No Longer Listed")

    save_snapshot(cid, current_events)


def main() -> None:
    # Optionally filter to specific calendars via CLI args: python scraper.py javits
    requested = set(sys.argv[1:])
    targets = [s for s in scrapers.ALL if not requested or s.CALENDAR_ID in requested]

    if not targets:
        print(f"No matching scrapers for: {requested}", file=sys.stderr)
        sys.exit(1)

    for scraper in targets:
        run_scraper(scraper)


if __name__ == "__main__":
    main()
