"""
How often completed trials post results on ClinicalTrials.gov, by sponsor type.

  python tools/results_reporting.py [RAW_JSON]

RAW_JSON is the 1 October 2026 download (default data/raw/trials_raw.json).
Uses the published trials in data/powerbi/trials.csv (the 14,724-trial analysis set)
and three fields from the download that the tables do not keep: hasResults,
the primary completion date and the date results were first submitted.

Only completed trials whose primary completion date is on or before 30 September 2025
are counted, so every trial had at least a year to submit results before the download.
Rows are split by whether the trial lists a US site, since US law requires results
only for some trials, most of them run in the US. Writes results/10_results_reporting.csv.

Not every trial here is an "applicable clinical trial" under US law (FDAAA 801), so
these are reporting rates, not compliance rates.
"""

import csv
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUTOFF = date(2025, 9, 30)


def parse(d):
    """'2012-09' or '2012-09-14' -> date (a month alone counts as its 15th)."""
    if not d:
        return None
    parts = [int(p) for p in d.split("-")]
    return date(parts[0], parts[1], parts[2] if len(parts) > 2 else 15)


def months(a, b):
    return (b - a).days / 30.44


def main(raw):
    with open(ROOT / "data" / "powerbi" / "trials.csv", encoding="utf-8") as f:
        trials = {r["nct_id"]: r for r in csv.DictReader(f)}
    with open(ROOT / "data" / "powerbi" / "sites.csv", encoding="utf-8") as f:
        us = {r["nct_id"] for r in csv.DictReader(f) if r["country"] == "United States"}
    with open(raw, encoding="utf-8") as f:
        studies = json.load(f)

    groups = {}
    for s in studies:
        p = s["protocolSection"]
        t = trials.get(p["identificationModule"]["nctId"])
        if not t or t["overall_status"] != "COMPLETED":
            continue
        st = p["statusModule"]
        done = parse(st.get("primaryCompletionDateStruct", {}).get("date"))
        if not done or done > CUTOFF:
            continue
        key = (t["sponsor_type"], "yes" if t["nct_id"] in us else "no")
        g = groups.setdefault(key, {"completed": 0, "with_results": 0, "within_12": 0, "lags": []})
        g["completed"] += 1
        if s.get("hasResults"):
            g["with_results"] += 1
            sub = parse(st.get("resultsFirstSubmitDate"))
            if sub:
                lag = months(done, sub)
                g["lags"].append(lag)
                g["within_12"] += lag <= 12

    # Roll up to sponsor type, US site yes/no, and each sponsor type with and without a US site.
    def merge(parts):
        m = {"completed": 0, "with_results": 0, "within_12": 0, "lags": []}
        for g in parts:
            for k in ("completed", "with_results", "within_12"):
                m[k] += g[k]
            m["lags"] += g["lags"]
        return m

    order = sorted({k[0] for k in groups}, key=lambda n: -sum(g["completed"] for k, g in groups.items() if k[0] == n))
    combos = [("All", "all", merge(groups.values()))]
    combos += [("All", u, merge(g for k, g in groups.items() if k[1] == u)) for u in ("yes", "no")]
    for n in order:
        combos.append((n, "all", merge(g for k, g in groups.items() if k[0] == n)))
        combos += [(n, u, groups[(n, u)]) for u in ("yes", "no") if (n, u) in groups]

    rows = []
    for name, u, g in combos:
        rows.append({
            "sponsor_type": name,
            "us_site": u,
            "completed_trials": g["completed"],
            "with_results": g["with_results"],
            "pct_with_results": round(100 * g["with_results"] / g["completed"], 1),
            "pct_within_12_months": round(100 * g["within_12"] / g["completed"], 1),
            "median_months_to_submit": round(statistics.median(g["lags"]), 1) if g["lags"] else "",
        })
    out = ROOT / "results" / "10_results_reporting.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "raw" / "trials_raw.json")
