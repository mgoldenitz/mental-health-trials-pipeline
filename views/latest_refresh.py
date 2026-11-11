"""Latest refresh page: the newest weekly download next to the published counts."""
import pandas as pd
import plotly.express as px
import streamlit as st

import tracker as t


def compare(baseline, latest, metric):
    """Published and latest values of one metric side by side."""
    b = baseline[baseline["metric"] == metric].assign(category=lambda d: t.relabel(d["category"]))
    l = latest[latest["metric"] == metric].assign(category=lambda d: t.relabel(d["category"]))
    b, l = b.set_index("category")["value"], l.set_index("category")["value"]
    out = pd.DataFrame({"Published": b, "Latest": l}).fillna(0).astype(int)
    out["Change"] = out["Latest"] - out["Published"]
    out.index.name = None
    return out


# Same number style as the rest of the app: thousands separators, and a sign on the change
COMPARE_COLUMNS = {
    "Published": st.column_config.NumberColumn(format="localized"),
    "Latest": st.column_config.NumberColumn(format="localized"),
    "Change": st.column_config.NumberColumn(format="%+d"),
}


def one(df, metric, category="All"):
    row = df[(df["metric"] == metric) & (df["category"] == category)]
    return int(row["value"].iloc[0]) if len(row) else 0


st.subheader("Latest refresh")
refresh = t.weekly_refresh()
if refresh is None:
    st.info("This page shows counts from the latest weekly download next to the published "
            "counts from 1 October 2026. The scheduled refresh is not connected yet.")
elif refresh == "error":
    st.warning("The latest weekly refresh is unavailable right now. Please try again later.")
else:
    latest, manifest, history = refresh
    baseline = t.load_baseline()
    st.caption(f"Latest download: {manifest['snapshot_date']} · Published baseline: 1 October 2026 · "
               "Trials started 2010–2025")

    with st.grid(4, min_column_width=170, gap="small"):
        for label, metric, category in [
                ("Trials", "trials", "All"),
                ("Psychedelic / MDMA", "trials_by_drug_class", "Psychedelic / MDMA"),
                ("Ketamine / Esketamine", "trials_by_drug_class", "Ketamine / esketamine"),
                ("Canadian site", "trials_with_canadian_site", "All")]:
            now, then = one(latest, metric, category), one(baseline, metric, category)
            delta = now - then
            st.metric(label, f"{now:,}", f"{delta:+,} since publication" if delta else None,
                      delta_color="off")

    c1, c2 = st.columns(2)
    by_year = compare(baseline, latest, "trials_by_year").reset_index(names="start_year")
    by_year["start_year"] = by_year["start_year"].astype(int)
    fig = px.line(by_year.melt(id_vars="start_year", value_vars=["Published", "Latest"]),
                  x="start_year", y="value", color="variable", markers=True,
                  labels={"start_year": "Year started", "value": "Trials", "variable": ""},
                  title="Trials started each year")
    t.chart(c1, fig, alt="Line chart comparing trials started each year in the published download "
                         "and in the latest weekly download.")

    c2.markdown("Trials by condition")
    c2.dataframe(compare(baseline, latest, "trials_by_condition"), width="stretch",
                 column_config=COMPARE_COLUMNS, alt="Table of published and latest trial counts by condition group, with the change.")
    c2.markdown("Trials by outcome")
    c2.dataframe(compare(baseline, latest, "trials_by_outcome"), width="stretch",
                 column_config=COMPARE_COLUMNS, alt="Table of published and latest trial counts by outcome, with the change.")

    later = latest[latest["metric"] == "started_after_window"]
    totals = history[(history["metric"] == "trials") & (history["category"] == "All")].copy()
    totals["snapshot_date"] = pd.to_datetime(totals["snapshot_date"])
    totals = totals.sort_values("snapshot_date").drop_duplicates("snapshot_date", keep="last")
    if len(totals) >= 4:
        fig = px.line(totals, x="snapshot_date", y="value", markers=True,
                      labels={"snapshot_date": "Download date", "value": "Trials that began 2010–2025"},
                      title="Trials in the analysis window at each weekly download")
        fig.update_xaxes(tickformat="%b %d, %Y",
                         tickvals=totals["snapshot_date"] if len(totals) <= 12 else None)
        fig.update_yaxes(tickformat=",d", dtick=max(1, round((totals["value"].max()
                                                              - totals["value"].min()) / 5)))
        t.chart(st, fig)
    with st.expander("Refresh notes"):
        if len(later):
            later_counts = ", ".join(f"{r.category}: {r.value:,}" for r in later.itertuples())
            st.caption(f"{later_counts} trials list a start after 2025. Many dates are estimates; "
                       "these trials are outside the published analysis.")
        st.caption("Four newer condition groups are on the New condition groups page.")
        if len(totals) < 4:
            st.caption("Weekly trend appears after four downloads.")
