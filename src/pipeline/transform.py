"""Flatten studies into tables, build the Power BI tables and count the headline figures.

Mirrors notebook cells C1 to C5. Tables are lists of dicts so the Lambda
function needs no third-party packages.
"""

import csv
import io
import re
from collections import Counter

from .rules import GROUPS, NEW_GROUPS, drug_class, group_of, new_groups, suicide_flag

WINDOW = (2010, 2025)   # start years of the published analysis

COLUMNS = {
    "trials": ["nct_id", "title", "start_year", "overall_status", "why_stopped", "phase",
               "enrollment", "sponsor_name", "sponsor_class", "sponsor_type", "outcome",
               "scope", "suicide_flag"],
    "conditions": ["nct_id", "condition", "condition_group"],
    "interventions": ["nct_id", "intervention_type", "intervention_name",
                      "psychedelic_class", "treatment_type"],
    "sites": ["nct_id", "country"],
}

SPONSOR_TYPE = {"OTHER": "Universities & Hospitals", "INDUSTRY": "Companies",
                "FED": "US Federal", "NIH": "US Federal", "OTHER_GOV": "Other governments"}
OUTCOME = {"COMPLETED": "Completed", "TERMINATED": "Stopped Early",
           "WITHDRAWN": "Stopped Early", "SUSPENDED": "Stopped Early"}
TREATMENT_TYPE = {"DRUG": "Drug", "BEHAVIORAL": "Behavioural", "DEVICE": "Device"}


def g(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def flatten(studies, tables=None, search="core"):
    """Add studies to the four raw tables (cell C1). Call once per API page.

    search names the API search the page came from: "core" (fetch.QUERY_COND) or
    "extra" (fetch.EXTRA_COND). Run the core search first; a study the extra search
    returns again is skipped, so it stays marked as core.
    """
    tables = tables or {"trials": [], "conditions": [], "interventions": [], "sites": []}
    seen = tables.setdefault("seen", set())
    for s in studies:
        p = s.get("protocolSection", {})
        nct = g(p, "identificationModule", "nctId")
        if nct in seen:
            continue
        seen.add(nct)
        start = g(p, "statusModule", "startDateStruct", "date")
        tables["trials"].append({
            "search": search,
            "nct_id": nct,
            "title": g(p, "identificationModule", "briefTitle"),
            "start_year": int(start[:4]) if start else None,
            "overall_status": g(p, "statusModule", "overallStatus"),
            "why_stopped": g(p, "statusModule", "whyStopped"),
            "phase": "/".join(g(p, "designModule", "phases", default=[]) or []) or "NA",
            "enrollment": g(p, "designModule", "enrollmentInfo", "count"),
            "sponsor_name": g(p, "sponsorCollaboratorsModule", "leadSponsor", "name"),
            "sponsor_class": g(p, "sponsorCollaboratorsModule", "leadSponsor", "class"),
        })
        for c in g(p, "conditionsModule", "conditions", default=[]) or []:
            tables["conditions"].append({"nct_id": nct, "condition": c})
        for i in g(p, "armsInterventionsModule", "interventions", default=[]) or []:
            tables["interventions"].append({"nct_id": nct,
                                            "intervention_type": i.get("type"),
                                            "intervention_name": i.get("name")})
        locations = g(p, "contactsLocationsModule", "locations", default=[]) or []
        for country in sorted({loc.get("country") for loc in locations if loc.get("country")}):
            tables["sites"].append({"nct_id": nct, "country": country})
    return tables


def _one_line(row):
    # line breaks inside text break CSV readers
    return {k: re.sub(r"[\r\n]+", " ", v) if isinstance(v, str) else v for k, v in row.items()}


def powerbi(tables):
    """Group conditions, flag drugs and keep in-scope trials (cells C2, C3 and C5).

    Each condition gets its published group (rules.GROUPS, first match) and every v2
    group it matches (rules.NEW_GROUPS), one row each. A trial's scope is "core" when
    the core search returned it and it has a published group: exactly the trials of the
    published analysis. All other kept trials are "extended" and have only v2 groups.
    """
    conditions = []
    for c in tables["conditions"]:
        grp = group_of(c["condition"])
        if grp != "Other":
            conditions.append(dict(c, condition_group=grp))
        conditions += [dict(c, condition_group=new) for new in new_groups(c["condition"])]
    ids = {c["nct_id"] for c in conditions}

    search = {t["nct_id"]: t.get("search", "core") for t in tables["trials"]}
    core = {c["nct_id"] for c in conditions
            if c["condition_group"] in GROUPS and search.get(c["nct_id"]) == "core"}
    flagged = {c["nct_id"] for c in tables["conditions"] if suicide_flag(c["condition"])}

    trials = [dict(t, sponsor_type=SPONSOR_TYPE.get(t["sponsor_class"], "Other"),
                   outcome=OUTCOME.get(t["overall_status"], "Ongoing or Unknown"),
                   scope="core" if t["nct_id"] in core else "extended",
                   suicide_flag=t["nct_id"] in flagged or suicide_flag(t["title"]))
              for t in tables["trials"] if t["nct_id"] in ids]
    interventions = [dict(i, psychedelic_class=drug_class(i["intervention_name"]),
                          treatment_type=TREATMENT_TYPE.get(i["intervention_type"], "Other"))
                     for i in tables["interventions"] if i["nct_id"] in ids]
    sites = [s for s in tables["sites"] if s["nct_id"] in ids]

    out = {"trials": trials, "conditions": conditions,
           "interventions": interventions, "sites": sites}
    return {name: [_one_line(r) for r in rows] for name, rows in out.items()}


def counts(pb):
    """Headline figures for the refresh page, as rows of (metric, category, value).

    Everything except the "started_after_window" rows uses trials that started
    2010-2025, the published window, so a change against the baseline means the
    registry changed, not that a year was added.
    """
    lo, hi = WINDOW
    year = {t["nct_id"]: t["start_year"] for t in pb["trials"]}
    all_window = {n for n, y in year.items() if y is not None and lo <= y <= hi}
    # The published metrics use the core trials only, so they compare with the baseline
    core = {t["nct_id"] for t in pb["trials"] if t["scope"] == "core"}
    in_window = all_window & core
    trials = [t for t in pb["trials"] if t["nct_id"] in in_window]

    rows = [("trials", "All", len(trials))]
    rows += [("trials_by_year", str(y), n)
             for y, n in sorted(Counter(t["start_year"] for t in trials).items())]

    by_group = {(c["nct_id"], c["condition_group"]) for c in pb["conditions"]
                if c["nct_id"] in in_window and c["condition_group"] in GROUPS}
    rows += [("trials_by_condition", grp, n)
             for grp, n in sorted(Counter(grp for _, grp in by_group).items())]
    rows += [("trials_by_condition_year", f"{grp}|{y}", n) for (grp, y), n in
             sorted(Counter((grp, year[nct]) for nct, grp in by_group).items())]

    for metric, col in [("trials_by_outcome", "outcome"), ("trials_by_status", "overall_status"),
                        ("trials_by_sponsor_type", "sponsor_type")]:
        rows += [(metric, k, n) for k, n in sorted(Counter(t[col] for t in trials).items())]

    typed = {(i["nct_id"], i["treatment_type"]) for i in pb["interventions"]
             if i["nct_id"] in in_window}
    rows += [("trials_by_treatment_type", k, n)
             for k, n in sorted(Counter(k for _, k in typed).items())]

    flagged = {(i["nct_id"], i["psychedelic_class"]) for i in pb["interventions"]
               if i["nct_id"] in in_window and i["psychedelic_class"]}
    rows += [("trials_by_drug_class", k, n)
             for k, n in sorted(Counter(k for _, k in flagged).items())]

    canada = {s["nct_id"] for s in pb["sites"] if s["country"] == "Canada" and s["nct_id"] in in_window}
    rows.append(("trials_with_canadian_site", "All", len(canada)))

    later = Counter(y for n, y in year.items() if n in core and y is not None and y > hi)
    rows += [("started_after_window", str(y), n) for y, n in sorted(later.items())]

    # v2 groups and the suicide flag: every kept trial in the window, core or extended
    rows.append(("v2_trials_all_scopes", "All", len(all_window)))
    rows.append(("v2_trials_extended", "All", len(all_window - core)))
    new = {(c["nct_id"], c["condition_group"]) for c in pb["conditions"]
           if c["nct_id"] in all_window and c["condition_group"] in NEW_GROUPS}
    rows += [("v2_trials_by_new_condition", grp, n)
             for grp, n in sorted(Counter(grp for _, grp in new).items())]
    rows += [("v2_trials_by_new_condition_year", f"{grp}|{y}", n) for (grp, y), n in
             sorted(Counter((grp, year[nct]) for nct, grp in new).items())]
    flagged = {t["nct_id"] for t in pb["trials"] if t["suicide_flag"] and t["nct_id"] in all_window}
    rows.append(("v2_trials_with_suicide_flag", "All", len(flagged)))
    every = {(c["nct_id"], c["condition_group"]) for c in pb["conditions"] if c["nct_id"] in flagged}
    rows += [("v2_suicide_flag_by_condition", grp, n)
             for grp, n in sorted(Counter(grp for _, grp in every).items())]
    return [{"metric": m, "category": c, "value": v} for m, c, v in rows]


def to_csv(rows, columns):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
