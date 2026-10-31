"""
Check that the refresh pipeline reproduces the published tables.

  python tools/check_against_published.py OUT_DIR

OUT_DIR holds tables the pipeline rebuilt from the 1 October 2026 download
(python -m pipeline --raw ... --out OUT_DIR, run from src/). Each table is
compared with data/powerbi/ value by value, ignoring row order.
"""

import sys
from pathlib import Path

import pandas as pd

PUBLISHED = Path(__file__).resolve().parent.parent / "data" / "powerbi"


def main(out):
    ok = True
    for name in ["trials", "conditions", "interventions", "sites"]:
        a = pd.read_csv(PUBLISHED / f"{name}.csv")
        b = pd.read_csv(Path(out) / f"{name}.csv")
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
    main(sys.argv[1])
