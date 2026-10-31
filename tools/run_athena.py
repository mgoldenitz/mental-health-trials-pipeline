"""
Run the queries in athena/ and save each result as CSV.

  python tools/run_athena.py [--database mental_health_trials] [--profile personal]

  --database mental_health_trials             the newest weekly refresh (default)
  --database mental_health_trials_published   the published download of 1 October 2026;
                                              add --compare to check against results/

Results go to out/athena/<database>/. The script prints the data each query
scanned; Athena charges USD 5 per TB, with a 10 MB minimum per query.
Needs boto3 (and pandas for --compare).
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent


def run(athena, sql, database, workgroup):
    qid = athena.start_query_execution(QueryString=sql, WorkGroup=workgroup,
                                       QueryExecutionContext={"Database": database})["QueryExecutionId"]
    while True:
        q = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = q["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if state != "SUCCEEDED":
        raise RuntimeError(q["Status"].get("StateChangeReason", state))
    rows = []
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        rows += [[c.get("VarCharValue", "") for c in r["Data"]] for r in page["ResultSet"]["Rows"]]
    return rows, q["Statistics"]["DataScannedInBytes"]


def same(path_a, path_b):
    import pandas as pd
    a, b = pd.read_csv(path_a), pd.read_csv(path_b)
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return False
    # rows tied on the ORDER BY column can come back in any order
    a = a.sort_values(list(a.columns)).reset_index(drop=True)
    b = b.sort_values(list(b.columns)).reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
        return True
    except AssertionError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", default="mental_health_trials")
    ap.add_argument("--workgroup", default="trials-refresh")
    ap.add_argument("--profile")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--compare", action="store_true", help="compare each result with results/")
    args = ap.parse_args()

    athena = boto3.Session(profile_name=args.profile, region_name=args.region).client("athena")
    out = ROOT / "out" / "athena" / args.database
    out.mkdir(parents=True, exist_ok=True)
    total, differ = 0, 0
    for path in sorted((ROOT / "athena").glob("*.sql")):
        rows, scanned = run(athena, path.read_text(encoding="utf-8"), args.database, args.workgroup)
        total += scanned
        dest = out / f"{path.stem}.csv"
        with open(dest, "w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
        line = f"{path.stem:38s} {len(rows) - 1:>4} rows  {scanned / 1e6:6.2f} MB scanned"
        if args.compare:
            ok = same(dest, ROOT / "results" / f"{path.stem}.csv")
            differ += not ok
            line += "  matches results/" if ok else "  DIFFERS from results/"
        print(line)
    print(f"Total scanned: {total / 1e6:.2f} MB")
    sys.exit(1 if differ else 0)


if __name__ == "__main__":
    main()
