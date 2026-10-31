"""
Upload the published tables (download of 1 October 2026) as Parquet, so Athena
can query them in the mental_health_trials_published database.

  python tools/upload_published_parquet.py BUCKET [--profile personal]

Run once from the repository root. It reads data/powerbi/*.csv and writes
s3://BUCKET/athena/published/<table>/<table>.parquet. Needs boto3 and pyarrow:

  uv run --with boto3 --with "botocore[crt]" --with pyarrow python tools/upload_published_parquet.py BUCKET --profile personal
"""

import argparse
import csv
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from pipeline.parquet import SCHEMAS, to_parquet  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bucket")
    ap.add_argument("--profile")
    args = ap.parse_args()

    s3 = boto3.Session(profile_name=args.profile).client("s3")
    for name in SCHEMAS:
        with open(ROOT / "data" / "powerbi" / f"{name}.csv", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        key = f"athena/published/{name}/{name}.parquet"
        s3.put_object(Bucket=args.bucket, Key=key, Body=to_parquet(rows, name),
                      ContentType="application/vnd.apache.parquet")
        print(f"{name:14s} {len(rows):>8,} rows -> s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
