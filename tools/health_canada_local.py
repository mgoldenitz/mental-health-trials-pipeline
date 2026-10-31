"""
Run the Health Canada step on your own computer, without AWS.

  python tools/health_canada_local.py --out out/hc
      download the three API endpoints, then build the tables

  python tools/health_canada_local.py --raw-dir DIR --out out/hc
      build the tables from protocol.json, drugproduct.json and status.json in DIR
      (status.json may be missing; the codes are then left as numbers)

Writes hc_trials.csv, hc_conditions.csv, hc_drugs.csv and counts.csv to --out, and
lists every condition name that the mental health rules matched, so you can check them.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pipeline import health_canada as hc   # noqa: E402
from pipeline.transform import to_csv       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", help="folder with saved endpoint JSON files")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    raw = {}
    for name in hc.ENDPOINTS:
        if args.raw_dir:
            f = Path(args.raw_dir) / f"{name}.json"
            raw[name] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        else:
            t = time.time()
            raw[name] = hc.get_json(name)
            (out / f"{name}.json").write_text(json.dumps(raw[name]), encoding="utf-8")
            print(f"{name}: {len(raw[name]):,} records in {time.time() - t:.0f} s")

    tables = hc.build(raw)
    for name, rows in tables.items():
        (out / f"{name}.csv").write_text(to_csv(rows, hc.COLUMNS[name]), encoding="utf-8")
        print(f"{name:14s} {len(rows):>7,} rows")
    counts = hc.counts(tables, len(raw["protocol"]))
    (out / "counts.csv").write_text(to_csv(counts, ["metric", "category", "value"]), encoding="utf-8")

    matched = Counter((c["condition_group"], c["condition"]) for c in tables["hc_conditions"]
                      if c["condition_group"] != "Other")
    (out / "matched_conditions.csv").write_text(
        to_csv([{"condition_group": g, "condition": c, "trials": n}
                for (g, c), n in sorted(matched.items())],
               ["condition_group", "condition", "trials"]), encoding="utf-8")
    print(f"{len(raw['protocol']):,} protocols, {len(tables['hc_trials']):,} mental health; "
          f"{len(matched):,} distinct matched condition names in matched_conditions.csv")


if __name__ == "__main__":
    main()
