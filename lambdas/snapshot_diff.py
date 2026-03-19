"""
Snapshot Diff Lambda — testing/debugging tool

Fetches two versioned S3 snapshots for a calendar and returns the diff.

Event input:
  {
    "calendar_id": "javits",          # required
    "version_id_old": "abc123...",    # optional — defaults to second-latest
    "version_id_new": "def456..."     # optional — defaults to latest
  }
"""

import json
import os

import boto3
from botocore.exceptions import ClientError

SNAPSHOT_BUCKET = os.environ["SNAPSHOT_BUCKET"]

s3 = boto3.client("s3")


def snapshot_key(calendar_id: str) -> str:
    return f"{calendar_id}/events_snapshot.json"


def list_versions(calendar_id: str) -> list[dict]:
    """Return all versions of a snapshot, newest first."""
    key = snapshot_key(calendar_id)
    resp = s3.list_object_versions(Bucket=SNAPSHOT_BUCKET, Prefix=key)
    versions = [
        v for v in resp.get("Versions", [])
        if v["Key"] == key
    ]
    versions.sort(key=lambda v: v["LastModified"], reverse=True)
    return versions


def fetch_version(calendar_id: str, version_id: str) -> dict:
    obj = s3.get_object(
        Bucket=SNAPSHOT_BUCKET,
        Key=snapshot_key(calendar_id),
        VersionId=version_id,
    )
    return json.loads(obj["Body"].read().decode("utf-8"))


def diff_snapshots(old: dict, new: dict) -> dict:
    old_events = {e.get("id", e["title"]): e for e in old.get("events", [])}
    new_events = {e.get("id", e["title"]): e for e in new.get("events", [])}

    added = [e for k, e in new_events.items() if k not in old_events]
    removed = [e for k, e in old_events.items() if k not in new_events]

    return {"added": added, "removed": removed}


def handler(event, context):
    calendar_id = event.get("calendar_id")
    if not calendar_id:
        return {"statusCode": 400, "body": json.dumps({"error": "calendar_id is required"})}

    try:
        versions = list_versions(calendar_id)
    except ClientError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    if len(versions) < 2:
        return {
            "statusCode": 404,
            "body": json.dumps({
                "error": f"Need at least 2 versions to diff, found {len(versions)} for '{calendar_id}'"
            }),
        }

    version_id_new = event.get("version_id_new") or versions[0]["VersionId"]
    version_id_old = event.get("version_id_old") or versions[1]["VersionId"]

    try:
        snap_old = fetch_version(calendar_id, version_id_old)
        snap_new = fetch_version(calendar_id, version_id_new)
    except ClientError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    diff = diff_snapshots(snap_old, snap_new)

    result = {
        "calendar_id": calendar_id,
        "old_version": {
            "version_id": version_id_old,
            "scraped_at": snap_old.get("scraped_at"),
            "total_events": len(snap_old.get("events", [])),
        },
        "new_version": {
            "version_id": version_id_new,
            "scraped_at": snap_new.get("scraped_at"),
            "total_events": len(snap_new.get("events", [])),
        },
        "added_count": len(diff["added"]),
        "removed_count": len(diff["removed"]),
        "added": diff["added"],
        "removed": diff["removed"],
        "available_versions": [
            {"version_id": v["VersionId"], "last_modified": v["LastModified"].isoformat()}
            for v in versions
        ],
    }

    return {"statusCode": 200, "body": json.dumps(result, ensure_ascii=False, indent=2)}
