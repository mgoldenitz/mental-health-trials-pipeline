"""
Run the pipeline on your own computer, without AWS.

  python -m pipeline --raw ../data/raw/trials_raw.json --out ../out/2026-10-01
      rebuild the tables from a saved download (reproduces the published tables)

  python -m pipeline --fetch --out ../out/today
      download fresh data and report how long the download took

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
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    began = time.time()
    manifest = {}

    if args.raw:
        with open(args.raw) as f:
            tables = transform.flatten(json.load(f))
        manifest["source"] = args.raw
    else:
        tables, n = None, 0
        for page in fetch.pages(end=args.end):
            manifest.setdefault("api_total", page.get("totalCount"))
            tables = transform.flatten(page["studies"], tables)
            n += len(page["studies"])
            print(f"{n:,} downloaded ({time.time() - began:.0f} s)")
        manifest.update(downloaded=n, end=args.end, download_seconds=round(time.time() - began))

    pb = transform.powerbi(tables)
    for name, rows in pb.items():
        (out / f"{name}.csv").write_text(transform.to_csv(rows, transform.COLUMNS[name]))
        print(f"{name:14s} {len(rows):>8,} rows")
    (out / "counts.csv").write_text(
        transform.to_csv(transform.counts(pb), ["metric", "category", "value"]))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Done in {time.time() - began:.0f} s; files in {out}")


if __name__ == "__main__":
    main()
