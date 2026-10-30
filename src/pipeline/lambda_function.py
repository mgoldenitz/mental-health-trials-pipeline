"""
AWS Lambda entry point: download, clean and count, then save a dated snapshot to S3.

S3 layout (BUCKET environment variable):
  raw/<date>/page-0001.json.gz ...   API pages exactly as downloaded
  snapshots/<date>/<table>.csv       the four Power BI tables
  snapshots/<date>/counts.csv        headline figures (metric, category, value)
  snapshots/<date>/manifest.json     what was downloaded and checks passed
  latest/                            copies of the newest counts.csv and manifest.json
  history/counts.csv                 every snapshot's counts, one block per date

Nothing is overwritten except latest/ and history/counts.csv. The published
analysis (1 October 2026) is not in S3; it stays in the repository.
"""

import gzip
import json
import os
import time
from datetime import date, datetime, timezone

import boto3

from . import fetch, transform

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]
MAX_DROP = float(os.environ.get("MAX_DROP", "0.10"))   # fail if in-window trials fall by more than this


def put(key, body, content_type="text/csv"):
    s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=content_type)


def get_text(key):
    try:
        return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()
    except s3.exceptions.NoSuchKey:
        return None


def handler(event, context):
    began = time.time()
    today = datetime.now(timezone.utc).date().isoformat()
    end = os.environ.get("END_DATE") or f"{date.today().year}-12-31"

    # 1. Download page by page, saving each raw page before cleaning it
    tables, total, n = None, None, 0
    for i, page in enumerate(fetch.pages(end=end), start=1):
        if total is None:
            total = page.get("totalCount")
        put(f"raw/{today}/page-{i:04d}.json.gz",
            gzip.compress(json.dumps(page["studies"]).encode()), "application/gzip")
        tables = transform.flatten(page["studies"], tables)
        n += len(page["studies"])
        print(f"page {i}: {n:,} of {total:,} studies, {time.time() - began:.0f} s")
        if context.get_remaining_time_in_millis() < 60_000:
            raise TimeoutError(f"Stopped after {n:,} of {total:,} studies: under a minute left. "
                               "Raise the function timeout or move the job to ECS Fargate.")

    # 2. The same check as the notebook: every study the API reported was downloaded
    if n != total:
        raise ValueError(f"Downloaded {n:,} studies but the API reported {total:,}")

    pb = transform.powerbi(tables)
    counts = transform.counts(pb)
    in_window = next(r["value"] for r in counts if r["metric"] == "trials")

    # 3. Refuse a snapshot that lost more than MAX_DROP of the trials since the last one
    last = get_text("latest/manifest.json")
    if last:
        before = json.loads(last)["trials_in_window"]
        if in_window < before * (1 - MAX_DROP):
            raise ValueError(f"Trials in window fell from {before:,} to {in_window:,}; "
                             "check the API before trusting this snapshot")

    # 4. Save the snapshot, then point latest/ at it
    for name, rows in pb.items():
        put(f"snapshots/{today}/{name}.csv", transform.to_csv(rows, transform.COLUMNS[name]))
    counts_csv = transform.to_csv(counts, ["metric", "category", "value"])
    manifest = {"snapshot_date": today, "start_range": ["2010-01-01", end],
                "api_total": total, "downloaded": n, "trials_in_window": in_window,
                "pages": i, "seconds": round(time.time() - began)}
    put(f"snapshots/{today}/counts.csv", counts_csv)
    put(f"snapshots/{today}/manifest.json", json.dumps(manifest, indent=2), "application/json")
    put("latest/counts.csv", counts_csv)
    put("latest/manifest.json", json.dumps(manifest, indent=2), "application/json")

    # 5. Add this snapshot to the history, replacing an earlier run from the same day
    history = get_text("history/counts.csv") or "snapshot_date,metric,category,value\n"
    lines = [l for l in history.splitlines()[1:] if not l.startswith(today + ",")]
    dated = [dict(r, snapshot_date=today) for r in counts]
    new = transform.to_csv(dated, ["snapshot_date", "metric", "category", "value"]).splitlines()
    put("history/counts.csv", "\n".join([new[0]] + lines + new[1:]) + "\n")

    print(json.dumps(manifest))
    return manifest
