"""
Event Calendar Scraper — AWS Lambda handler
Runs every registered scraper, diffs against the S3 snapshot, logs changes.
"""

import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import scrapers

SNAPSHOT_BUCKET = os.environ["SNAPSHOT_BUCKET"]

s3 = boto3.client("s3")


def snapshot_key(calendar_id: str) -> str:
    return f"{calendar_id}/events_snapshot.json"


def load_snapshot(calendar_id: str) -> dict:
    try:
        obj = s3.get_object(Bucket=SNAPSHOT_BUCKET, Key=snapshot_key(calendar_id))
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "NoSuchBucket"):
            return {}
        raise


def save_snapshot(calendar_id: str, events: list[dict]) -> None:
    data = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }
    key = snapshot_key(calendar_id)
    s3.put_object(
        Bucket=SNAPSHOT_BUCKET,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"[{calendar_id}] Snapshot saved → s3://{SNAPSHOT_BUCKET}/{key} ({len(events)} events)")


def find_new_events(previous: list[dict], current: list[dict]) -> list[dict]:
    prev_keys = {(e["title"], e["date"]) for e in previous}
    return [e for e in current if (e["title"], e["date"]) not in prev_keys]


def run_scraper(scraper) -> dict:
    cid = scraper.CALENDAR_ID
    name = scraper.CALENDAR_NAME

    print(f"[{cid}] Scraping {name} ...")
    current_events = scraper.fetch_events()
    print(f"[{cid}] Fetched {len(current_events)} events.")

    snapshot = load_snapshot(cid)
    previous_events: list[dict] = snapshot.get("events", []) if isinstance(snapshot, dict) else []
    previous_scraped_at: str = snapshot.get("scraped_at", "never")

    new_events = find_new_events(previous_events, current_events)
    removed_events = find_new_events(current_events, previous_events)

    if new_events:
        print(f"[{cid}] NEW ({len(new_events)}):")
        for e in new_events:
            print(f"[{cid}]   + {e['title']} | {e['date']} | {e['link']}")
    else:
        print(f"[{cid}] No new events since last scrape.")

    if removed_events:
        print(f"[{cid}] REMOVED ({len(removed_events)}):")
        for e in removed_events:
            print(f"[{cid}]   - {e['title']} | {e['date']}")

    save_snapshot(cid, current_events)

    return {
        "calendar_id": cid,
        "calendar_name": name,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "previous_scraped_at": previous_scraped_at,
        "total_events": len(current_events),
        "new_events_count": len(new_events),
        "removed_events_count": len(removed_events),
        "new_events": new_events,
        "removed_events": removed_events,
    }


def handler(event, context):
    results = []
    errors = []

    for scraper in scrapers.ALL:
        try:
            results.append(run_scraper(scraper))
        except Exception as e:
            print(f"[{scraper.CALENDAR_ID}] ERROR: {e}")
            errors.append({"calendar_id": scraper.CALENDAR_ID, "error": str(e)})

    status = 200 if not errors else 207
    return {
        "statusCode": status,
        "body": json.dumps({"results": results, "errors": errors}),
    }
