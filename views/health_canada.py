"""Health Canada page: mental health trials in the Health Canada Clinical Trials Database."""
import pandas as pd
import plotly.express as px
import streamlit as st

import tracker as t

st.subheader("Trials authorized by Health Canada")
conn = t.s3()
hc = None
if conn is not None:
    try:
        hc = t.load_health_canada(*conn)
    except Exception as exc:
        t.log_error("Health Canada data", exc)
        hc = "error"

if hc is None:
    st.info("This page shows mental health trials authorized by Health Canada. "
            "The scheduled refresh is not connected yet.")
elif hc == "error":
    st.warning("The Health Canada data is unavailable right now. Please try again later.")
else:
    hc_counts, hc_manifest, hc_trials = hc
    st.caption(
        f"Health Canada Clinical Trials Database, downloaded {hc_manifest['snapshot_date']}. "
        "It lists drug and biologic trials authorized by Health Canada since April 2013, including "
        "trials not registered on ClinicalTrials.gov. A trial counts when any of its conditions "
        "falls in one of the eight mental health groups.")
    st.caption("Health Canada trial counts overlap with the ‘In Canada’ ClinicalTrials.gov count on the "
               "Explore pages; do not add the two counts together.")

    def hc_metric(metric):
        out = hc_counts[hc_counts["metric"] == metric][["category", "value"]].copy()
        out["category"] = t.relabel(out["category"].astype(str))
        return out

    def hc_one(metric, category="All"):
        row = hc_counts[(hc_counts["metric"] == metric) & (hc_counts["category"] == category)]
        return int(row["value"].iloc[0]) if len(row) else 0

    status = hc_metric("hc_trials_by_status").set_index("category")["value"]
    drug = hc_metric("hc_trials_by_drug_class")
    with st.grid(4, min_column_width=165, gap="small"):
        st.metric("Mental health trials", f"{hc_one('hc_trials'):,}")
        st.metric("All authorized trials", f"{hc_one('hc_all_trials'):,}")
        st.metric("Ongoing", f"{int(status.get('Ongoing', 0)):,}")
        st.metric("Psychedelic & Ketamine", f"{int(drug['value'].sum()):,}")

    c1, c2 = st.columns(2)
    by_cond = hc_metric("hc_trials_by_condition").sort_values("value")
    fig = px.bar(by_cond, x="value", y="category", orientation="h",
                 labels={"value": "Trials", "category": ""},
                 title="Health Canada trials, by condition")
    t.chart(c1, fig)
    by_year = hc_metric("hc_trials_by_year").copy()
    by_year["category"] = pd.to_numeric(by_year["category"], errors="coerce")
    fig = px.bar(by_year.dropna(), x="category", y="value",
                 labels={"category": "Year approved", "value": "Trials"},
                 title="Health Canada trials, by year approved")
    t.chart(c2, fig)

    if hc_trials is not None:
        st.markdown("Ongoing Health Canada trials")
        ongoing = (hc_trials[hc_trials["status"] == "Ongoing"]
                   .sort_values("approved_date", ascending=False)
                   .assign(condition_group=lambda d: t.relabel(d["condition_group"].fillna(""))))
        st.dataframe(
            ongoing[["control_number", "title", "condition_group", "approved_date",
                     "sponsor_name", "psychedelic_class"]],
            column_config={
                "control_number": "Control number",
                "title": st.column_config.TextColumn("Title", width="large"),
                "condition_group": "Condition", "approved_date": "Approved",
                "sponsor_name": "Sponsor", "psychedelic_class": "Drug class",
            },
            hide_index=True, width="stretch",
            alt="Table of ongoing mental health trials authorized by Health Canada, newest approval first.")
