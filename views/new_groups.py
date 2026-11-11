"""New condition groups page: ADHD, autism, personality disorders, gambling and gaming."""
import pandas as pd
import plotly.express as px
import streamlit as st

import tracker as t

st.subheader("New condition groups")
refresh = t.weekly_refresh()
if refresh is None:
    st.info("This page shows ADHD, autism spectrum, personality disorder and gambling or gaming "
            "trials from the weekly download. The scheduled refresh is not connected yet.")
elif refresh == "error":
    st.warning("The latest weekly refresh is unavailable right now. Please try again later.")
else:
    latest, manifest, _ = refresh
    new = latest[latest["metric"] == "v2_trials_by_new_condition"]
    if new.empty:
        st.info("The latest weekly download does not include the new condition groups yet.")
    else:
        st.markdown(f"**Updated weekly.** Latest download: {manifest['snapshot_date']}.")
        st.caption("These four groups come from a second ClinicalTrials.gov search added in November 2026. "
                   "They are not part of the published analysis of 1 October 2026, so the counts on the "
                   "other pages do not include them, and these numbers change every Monday. Trials that "
                   "began between 2010 and 2025. A trial can be in more than one group, including a "
                   "published one.")

        def one_new(metric, category="All"):
            row = latest[(latest["metric"] == metric) & (latest["category"] == category)]
            return int(row["value"].iloc[0]) if len(row) else 0

        counts_new = new.set_index("category")["value"].astype(int)
        with st.grid(len(counts_new), min_column_width=165, gap="small"):
            for grp, n in counts_new.sort_values(ascending=False).items():
                st.metric(grp, f"{n:,}")

        c1, c2 = st.columns(2)
        yearly = latest[latest["metric"] == "v2_trials_by_new_condition_year"].copy()
        if len(yearly):
            yearly[["group", "start_year"]] = yearly["category"].str.split("|", n=1, expand=True)
            yearly["start_year"] = pd.to_numeric(yearly["start_year"], errors="coerce")
            yearly = yearly.dropna(subset=["start_year"]).rename(columns={"value": "trials"})
            fig = px.line(yearly, x="start_year", y="trials", color="group", markers=True,
                          color_discrete_map=t.new_group_colours(),
                          category_orders={"group": t.by_last_value(yearly, "start_year", "trials", "group")},
                          labels={"start_year": "Year started", "trials": "Trials", "group": ""},
                          title="Trials started each year, by New group")
            t.chart(c1, fig, alt="Line chart of trials started each year in the four new condition groups.")

        flags = (latest[latest["metric"] == "v2_suicide_flag_by_condition"]
                 .rename(columns={"category": "group", "value": "trials"})
                 .assign(group=lambda d: t.relabel(d["group"])))
        if len(flags):
            fig = px.bar(flags.sort_values("trials"), x="trials", y="group", orientation="h",
                         labels={"trials": "Trials", "group": ""},
                         title="Trials flagged for suicide or self-harm, by Condition group")
            t.chart(c2, fig)

        m1, m2 = st.columns(2)
        m1.metric("Trials not in the published analysis", f"{one_new('v2_trials_extended'):,}",
                  help="Trials in the 2010–2025 window that are not among the 14,724 published trials, "
                       "most of them found by the second search.")
        m2.metric("Trials flagged for suicide or self-harm", f"{one_new('v2_trials_with_suicide_flag'):,}",
                  help="Any trial in the window, published or new groups, whose conditions or title "
                       "mention suicide, self-harm or self-injury.")
