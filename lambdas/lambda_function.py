"""
Event Calendar Scraper — AWS Lambda handlers

worker_handler      — runs a single scraper (invoked by orchestrator)
orchestrator_handler — fans out to all workers in parallel, sends one email
"""

import concurrent.futures
import hashlib
import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import scrapers

SNAPSHOT_BUCKET = os.environ["SNAPSHOT_BUCKET"]

s3 = boto3.client("s3")
ses = boto3.client("ses")
lambda_client = boto3.client("lambda")


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

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


def make_event_id(title: str) -> str:
    return hashlib.sha1(title.strip().lower().encode()).hexdigest()[:12]


def find_new_events(previous: list[dict], current: list[dict]) -> list[dict]:
    prev_ids = {e["id"] for e in previous if "id" in e} | {e["title"] for e in previous if "id" not in e}
    return [e for e in current if e.get("id", e.get("title")) not in prev_ids]


def run_scraper(scraper) -> dict:
    cid = scraper.CALENDAR_ID
    name = scraper.CALENDAR_NAME

    print(f"[{cid}] Scraping {name} ...")
    current_events = scraper.fetch_events()
    print(f"[{cid}] Fetched {len(current_events)} events.")

    for e in current_events:
        e.setdefault("id", make_event_id(e["title"]))

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


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def build_email(results: list[dict]) -> tuple[str, str]:
    total_new = sum(r["new_events_count"] for r in results)
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"{total_new} New Event{'s' if total_new != 1 else ''} Found — {now}"

    sections = []
    for r in results:
        if not r["new_events"]:
            continue
        rows = ""
        for e in r["new_events"]:
            link_html = f'<a href="{e["link"]}">{e["link"]}</a>' if e["link"] else "—"
            desc = e["description"][:200] + "…" if len(e.get("description", "")) > 200 else e.get("description", "")
            rows += f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold">{e["title"]}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">{e["date"]}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;color:#555">{desc}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">{link_html}</td>
            </tr>"""
        sections.append(f"""
        <h2 style="color:#333;margin-top:32px">{r["calendar_name"]} — {r["new_events_count"]} new</h2>
        <table style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:14px">
          <thead>
            <tr style="background:#f5f5f5">
              <th style="padding:8px;text-align:left">Event</th>
              <th style="padding:8px;text-align:left">Dates</th>
              <th style="padding:8px;text-align:left">Description</th>
              <th style="padding:8px;text-align:left">Link</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    body = f"""
    <html><body style="font-family:sans-serif;color:#222;max-width:900px;margin:0 auto;padding:24px">
      <h1 style="color:#111">{total_new} New Event{'s' if total_new != 1 else ''} Found</h1>
      <p style="color:#666">Scraped on {now}</p>
      {"".join(sections)}
    </body></html>"""

    return subject, body


def send_notification(results: list[dict], test_mode: bool = False) -> None:
    if test_mode:
        notify_emails = ["dylanclark2396@gmail.com"]
        print("Test mode — sending only to dylanclark2396@gmail.com")
    else:
        notify_emails = [e.strip() for e in os.environ["NOTIFY_EMAIL"].split(",")]
    from_email = os.environ["FROM_EMAIL"]

    total_new = sum(r["new_events_count"] for r in results)
    if total_new == 0:
        print("No new events across any calendar — skipping email.")
        return

    subject, html_body = build_email(results)
    ses.send_email(
        Source=from_email,
        Destination={"ToAddresses": notify_emails},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Html": {"Data": html_body}},
        },
    )
    print(f"Notification sent to {notify_emails}: {subject}")


# ---------------------------------------------------------------------------
# Worker handler — runs one scraper, returns its result dict
# ---------------------------------------------------------------------------

def worker_handler(event, context):
    calendar_id = event["calendar_id"]
    scraper = next((s for s in scrapers.ALL if s.CALENDAR_ID == calendar_id), None)
    if scraper is None:
        raise ValueError(f"Unknown calendar_id: {calendar_id!r}")
    return run_scraper(scraper)


# ---------------------------------------------------------------------------
# Orchestrator handler — fans out to workers in parallel, sends one email
# ---------------------------------------------------------------------------

def _invoke_worker(worker_function_name: str, scraper) -> dict:
    resp = lambda_client.invoke(
        FunctionName=worker_function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"calendar_id": scraper.CALENDAR_ID}).encode(),
    )
    payload = json.loads(resp["Payload"].read())
    if resp.get("FunctionError"):
        error_msg = payload.get("errorMessage", "Unknown Lambda error")
        raise RuntimeError(error_msg)
    return payload


def orchestrator_handler(event, context):
    worker_function_name = os.environ["WORKER_FUNCTION_NAME"]
    test_mode = bool(event.get("test_mode", False))
    results = []
    errors = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_scraper = {
            executor.submit(_invoke_worker, worker_function_name, s): s
            for s in scrapers.ALL
        }
        for future, scraper in future_to_scraper.items():
            try:
                results.append(future.result())
            except Exception as e:
                print(f"[{scraper.CALENDAR_ID}] ERROR: {e}")
                errors.append({"calendar_id": scraper.CALENDAR_ID, "error": str(e)})

    send_notification(results, test_mode=test_mode)

    status = 200 if not errors else 207
    return {
        "statusCode": status,
        "body": json.dumps({"results": results, "errors": errors}),
    }
