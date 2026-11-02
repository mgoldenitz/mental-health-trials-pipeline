"""
Run the pipeline on your own computer, without AWS.

  python -m pipeline --raw ../data/raw/trials_raw.json --out ../out/2026-10-01
      rebuild the tables from a saved download (reproduces the published tables)

  python -m pipeline --fetch --out ../out/today
      download fresh data (both searches: the published conditions and the v2 groups)
      and report how long the download took

Add --parquet to also write each table as Parquet, as the Lambda function does
for Athena (needs pyarrow).

Run from the src/ folder.
"""

import argparse
import json
import time
from datetime import date
from pathlib import Path

from . import fetch, transform


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--raw", help="a saved download (JSON list of studies)")
    src.add_argument("--fetch", action="store_true", help="download from the API")
    ap.add_argument("--end", default=f"{date.today().year}-12-31",
                    help="last start date to download (default: end of this year)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--parquet", action="store_true", help="also write <table>.parquet (needs pyarrow)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    began = time.time()
    manifest = {}

    if args.raw:
        with open(args.raw, encoding="utf-8") as f:
            tables = transform.flatten(json.load(f))
        manifest["source"] = args.raw
    else:
        tables = None
        for search, cond, prefix in [("core", fetch.QUERY_COND, ""), ("extra", fetch.EXTRA_COND, "extra_")]:
            n = 0
            for page in fetch.pages(end=args.end, cond=cond):
                manifest.setdefault(f"{prefix}api_total", page.get("totalCount"))
                tables = transform.flatten(page["studies"], tables, search)
                n += len(page["studies"])
                print(f"{search} search: {n:,} downloaded ({time.time() - began:.0f} s)")
            manifest[f"{prefix}downloaded"] = n
        manifest.update(end=args.end, download_seconds=round(time.time() - began))

    pb = transform.powerbi(tables)
    for name, rows in pb.items():
        (out / f"{name}.csv").write_text(transform.to_csv(rows, transform.COLUMNS[name]), encoding="utf-8")
        if args.parquet:
            from . import parquet
            (out / f"{name}.parquet").write_bytes(parquet.to_parquet(rows, name))
        print(f"{name:14s} {len(rows):>8,} rows")
    (out / "counts.csv").write_text(
        transform.to_csv(transform.counts(pb), ["metric", "category", "value"]), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Done in {time.time() - began:.0f} s; files in {out}")


if __name__ == "__main__":
    main()
