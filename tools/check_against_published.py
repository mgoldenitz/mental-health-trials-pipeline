"""
Check that the refresh pipeline reproduces the published tables.

  python tools/check_against_published.py OUT_DIR [--sample RAW_JSON]

OUT_DIR holds tables the pipeline rebuilt from the 1 October 2026 download
(python -m pipeline --raw ... --out OUT_DIR, run from src/). Each table is
compared with data/powerbi/ value by value, ignoring row order.

Since v2 the rebuilt tables also hold extended-scope trials and the v2 condition
groups. With --sample RAW_JSON (used by CI with tests/fixtures/sample_raw.json.gz,
a 200-study extract of the download), the published tables are first cut to
the studies in RAW_JSON, so a trial the pipeline drops is still caught. Only core-scope trials and the published groups are compared, using the
published columns; the extra rows and columns are counted and reported.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from pipeline.rules import GROUPS  # noqa: E402

PUBLISHED = Path(__file__).resolve().parent.parent / "data" / "powerbi"


def main(out, sample=None):
    ok = True
    rebuilt = pd.read_csv(Path(out) / "trials.csv")
    core = set(rebuilt.loc[rebuilt["scope"] == "core", "nct_id"])
    print(f"core trials {len(core):,}; extended trials (not compared) {len(rebuilt) - len(core):,}")
    for name in ["trials", "conditions", "interventions", "sites"]:
        a = pd.read_csv(PUBLISHED / f"{name}.csv")
        if sample is not None:
            a = a[a["nct_id"].isin(sample)]
        b = pd.read_csv(Path(out) / f"{name}.csv")
        b = b[b["nct_id"].isin(core)]
        if name == "conditions":
            print(f"  v2 condition rows (not compared) {(~b['condition_group'].isin(GROUPS)).sum():,}")
            b = b[b["condition_group"].isin(GROUPS)]
        cols = list(a.columns)
        a = a.sort_values(cols).reset_index(drop=True)
        b = b[cols].sort_values(cols).reset_index(drop=True)
        try:
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
            print(f"{name:14s} matches ({len(a):,} rows)")
        except AssertionError as e:
            ok = False
            print(f"{name:14s} DIFFERS: {e}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    sample = None
    if "--sample" in sys.argv:
        import json
        with open(sys.argv[sys.argv.index("--sample") + 1], encoding="utf-8") as f:
            sample = {s["protocolSection"]["identificationModule"]["nctId"] for s in json.load(f)}
    main(sys.argv[1], sample)
