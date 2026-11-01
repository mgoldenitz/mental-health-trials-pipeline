"""
AWS Lambda entry point for the Health Canada refresh (runs after the ClinicalTrials.gov one).

S3 layout (BUCKET environment variable), all under health-canada/ so nothing touches
the ClinicalTrials.gov files:
  health-canada/raw/<date>/<endpoint>.json.gz        API responses exactly as downloaded
  health-canada/snapshots/<date>/<table>.csv         hc_trials, hc_conditions, hc_drugs
  health-canada/snapshots/<date>/counts.csv          headline figures (metric, category, value)
  health-canada/snapshots/<date>/manifest.json       what was downloaded and checks passed
  health-canada/latest/                              copies of the newest counts.csv and manifest.json
  health-canada/history/counts.csv                   every snapshot's counts, one block per date
  athena/health_canada/<table>/<table>.parquet       the newest three tables, read by Athena
"""

import gzip
import json
import os
import time
from datetime import datetime, timezone

import boto3

from . import health_canada as hc
from . import parquet
from .lambda_function import metrics_line
from .transform import to_csv

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]
MAX_DROP = float(os.environ.get("MAX_DROP", "0.10"))   # fail if all-trials count falls by more than this
NAMESPACE = os.environ.get("METRICS_NAMESPACE", "trials-refresh")
PREFIX = "health-canada/"


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

    # 1. Download each endpoint and save it before doing anything else
    raw = {}
    for name in hc.ENDPOINTS:
        t = time.time()
        raw[name] = hc.get_json(name)
        put(f"{PREFIX}raw/{today}/{name}.json.gz",
            gzip.compress(json.dumps(raw[name]).encode()), "application/gzip")
        print(f"{name}: {len(raw[name]):,} records in {time.time() - t:.0f} s")

    # 2. Checks: the endpoints returned lists of the expected records
    all_trials = len(raw["protocol"])
    if not all_trials or "protocol_id" not in raw["protocol"][0]:
        raise ValueError("The protocol endpoint returned no protocols")
    if not raw["status"] or "status_id" not in raw["status"][0]:
        raise ValueError("The status endpoint returned no status codes")

    last = get_text(f"{PREFIX}latest/manifest.json")
    before = None
    if last:
        before = json.loads(last)
        if all_trials < before["all_trials"] * (1 - MAX_DROP):
            raise ValueError(f"Health Canada trials fell from {before['all_trials']:,} to "
                             f"{all_trials:,}; check the API before trusting this snapshot")

    # 3. Build the mental health tables and save the snapshot
    tables = hc.build(raw)
    rows = hc.counts(tables, all_trials)
    for name, table in tables.items():
        put(f"{PREFIX}snapshots/{today}/{name}.csv", to_csv(table, hc.COLUMNS[name]))
    approved = sorted(p["nol_date"] for p in raw["protocol"] if p.get("nol_date"))
    manifest = {"snapshot_date": today, "all_trials": all_trials,
                "mental_health_trials": len(tables["hc_trials"]),
                "drug_rows": len(raw["drugproduct"]),
                "approved_range": [approved[0], approved[-1]] if approved else None,
                "seconds": round(time.time() - began)}
    counts_csv = to_csv(rows, ["metric", "category", "value"])
    manifest_json = json.dumps(manifest, indent=2)
    put(f"{PREFIX}snapshots/{today}/counts.csv", counts_csv)
    put(f"{PREFIX}snapshots/{today}/manifest.json", manifest_json, "application/json")
    put(f"{PREFIX}latest/counts.csv", counts_csv)
    put(f"{PREFIX}latest/manifest.json", manifest_json, "application/json")

    # 4. Parquet copies for Athena
    for name, table in tables.items():
        put(f"athena/health_canada/{name}/{name}.parquet",
            parquet.to_parquet(table, name, hc.SCHEMAS), "application/vnd.apache.parquet")

    # 5. History, replacing an earlier run from the same day
    history = get_text(f"{PREFIX}history/counts.csv") or "snapshot_date,metric,category,value\n"
    lines = [l for l in history.splitlines()[1:] if not l.startswith(today + ",")]
    new = to_csv([dict(r, snapshot_date=today) for r in rows],
                 ["snapshot_date", "metric", "category", "value"]).splitlines()
    put(f"{PREFIX}history/counts.csv", "\n".join([new[0]] + lines + new[1:]) + "\n")

    print(json.dumps(manifest))
    print(metrics_line(
        {"HcTrials": all_trials, "HcMentalHealthTrials": manifest["mental_health_trials"]},
        {"HcTrials": "Count", "HcMentalHealthTrials": "Count"}))
    return manifest
