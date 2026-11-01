"""
Health Canada clinical trials: download, keep the mental health trials, and build three tables.

Source: the Clinical Trials Database API, still updated after Health Canada moved the
public search to clinical-trials-search.canada.ca on 2026-07-29. Docs:
https://health-products.canada.ca/api/documentation/cta-documentation-en.html
Licence: Open Government Licence - Canada.

Each endpoint returns every record in one JSON list when called without an id. On
2026-10-31 these were 9,757 protocols (5.9 MB) and 9,816 drug product rows (1.7 MB).

  protocol     one row per approved trial: titles, dates, status code, conditions
  drugproduct  one row per drug in a trial: brand name and manufacturer (the sponsor)
  status       lookup for the protocol's status_id

The API has no phase, sites or ClinicalTrials.gov ID. Those are only in the portal's
CSV export, which takes about 14 minutes to build on Health Canada's side.

A trial counts as mental health when any of its conditions falls in one of the groups
in rules.GROUPS, the same rules used for the ClinicalTrials.gov tables.
"""

import json
import re
import time
import urllib.request

from .rules import drug_class, group_of

BASE = "https://health-products.canada.ca/api/clinical-trial/"
ENDPOINTS = ("protocol", "drugproduct", "status")

COLUMNS = {
    "hc_trials": ["control_number", "protocol_id", "protocol_number", "title", "approved_date",
                  "approved_year", "start_date", "end_date", "status", "sponsor_name",
                  "condition_group", "psychedelic_class"],
    "hc_conditions": ["control_number", "condition", "condition_group"],
    "hc_drugs": ["control_number", "brand_name", "manufacturer_name", "psychedelic_class"],
}

# Glue/Athena types, in the same order as COLUMNS; template.yaml lists the same columns
SCHEMAS = {
    "hc_trials": [("control_number", "string"), ("protocol_id", "bigint"),
                  ("protocol_number", "string"), ("title", "string"),
                  ("approved_date", "string"), ("approved_year", "int"),
                  ("start_date", "string"), ("end_date", "string"), ("status", "string"),
                  ("sponsor_name", "string"), ("condition_group", "string"),
                  ("psychedelic_class", "string")],
    "hc_conditions": [("control_number", "string"), ("condition", "string"),
                      ("condition_group", "string")],
    "hc_drugs": [("control_number", "string"), ("brand_name", "string"),
                 ("manufacturer_name", "string"), ("psychedelic_class", "string")],
}

# Health Canada condition names that the shared rules would put in a mental health group
# but that are not mental health: post-traumatic headaches and joint contractures
# (PTSD rule), opioid-induced constipation (substance use rule). Found in the
# 2026-10-31 download; kept here so the ClinicalTrials.gov tables stay as published.
HC_EXCLUDE = r"post\W*traumatic(?!\W*stress)|opioid\W*induced"

USER_AGENT = "mental-health-trials-pipeline (github.com/mgoldenitz/mental-health-trials-pipeline)"


def get_json(endpoint, timeout=300, tries=4):
    """Return one endpoint's full list. The protocol endpoint can take a few minutes."""
    url = f"{BASE}{endpoint}/?lang=en&type=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            break
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))   # 2, 4, 8 seconds
    # The 2017 docs show a {"result": ...} wrapper; the live API returns a bare list
    if isinstance(data, dict):
        data = data.get("result", data)
    if isinstance(data, dict):
        data = [data]
    return data


def download():
    return {name: get_json(name) for name in ENDPOINTS}


def condition_group(name):
    """rules.group_of, plus the Health Canada exclusions above."""
    if isinstance(name, str) and re.search(HC_EXCLUDE, name.lower()):
        return "Other"
    return group_of(name)


def _first_group(conditions):
    """The first mental health group among a trial's conditions, or None."""
    for c in conditions:
        grp = condition_group(c)
        if grp != "Other":
            return grp
    return None


def build(raw):
    """Turn the three raw lists into the three tables, mental health trials only."""
    status = {s.get("status_id"): (s.get("status") or "").title() for s in raw["status"]}

    drugs = {}
    for d in raw["drugproduct"]:
        drugs.setdefault(d.get("protocol_id"), []).append(d)

    tables = {name: [] for name in COLUMNS}
    for p in raw["protocol"]:
        conditions = [c.get("med_condition") for c in p.get("medConditionList") or []
                      if c.get("med_condition")]
        group = _first_group(conditions)
        if group is None:
            continue
        control = str(p.get("submission_no") or "")
        trial_drugs = drugs.get(p.get("protocol_id"), [])
        classes = {drug_class(d.get("brand_name")) for d in trial_drugs} - {None}
        if not classes and drug_class(p.get("protocol_title")):
            classes = {drug_class(p.get("protocol_title"))}
        approved = p.get("nol_date") or ""
        tables["hc_trials"].append({
            "control_number": control,
            "protocol_id": p.get("protocol_id"),
            "protocol_number": p.get("protocol_no"),
            "title": p.get("protocol_title"),
            "approved_date": approved,
            "approved_year": int(approved[:4]) if approved[:4].isdigit() else None,
            "start_date": p.get("start_date"),
            "end_date": p.get("end_date"),
            "status": status.get(p.get("status_id"), str(p.get("status_id"))),
            "sponsor_name": trial_drugs[0].get("manufacturer_name") if trial_drugs else None,
            "condition_group": group,
            "psychedelic_class": sorted(classes)[0] if classes else None,
        })
        for c in conditions:
            tables["hc_conditions"].append(
                {"control_number": control, "condition": c, "condition_group": condition_group(c)})
        for d in trial_drugs:
            tables["hc_drugs"].append({
                "control_number": control, "brand_name": d.get("brand_name"),
                "manufacturer_name": d.get("manufacturer_name"),
                "psychedelic_class": drug_class(d.get("brand_name")),
            })
    return tables


def counts(tables, all_trials):
    """Headline figures in the same metric,category,value shape as counts.csv."""
    from collections import Counter

    trials = tables["hc_trials"]
    rows = [("hc_all_trials", "All", all_trials), ("hc_trials", "All", len(trials))]
    for metric, col in [("hc_trials_by_year", "approved_year"), ("hc_trials_by_status", "status")]:
        rows += [(metric, str(k), n) for k, n in sorted(Counter(t[col] for t in trials).items(),
                                                        key=lambda kv: str(kv[0]))]
    groups = {(c["control_number"], c["condition_group"]) for c in tables["hc_conditions"]
              if c["condition_group"] != "Other"}
    rows += [("hc_trials_by_condition", g, n)
             for g, n in sorted(Counter(g for _, g in groups).items())]
    rows += [("hc_trials_by_drug_class", k, n) for k, n in
             sorted(Counter(t["psychedelic_class"] for t in trials if t["psychedelic_class"]).items())]
    return [{"metric": m, "category": c, "value": v} for m, c, v in rows]
