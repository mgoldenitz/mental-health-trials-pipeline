"""Psychedelic & Ketamine page."""
import plotly.express as px
import streamlit as st

import tracker as t

trials, conditions, interventions, sites = t.load_data()
view = t.filtered_view()
psy = view[view["psychedelic_class"].notna()]
if psy.empty:
    st.info("No psychedelic & Ketamine trials match the current filters.")
else:
    st.write("Trials testing a classic psychedelic or MDMA, or ketamine / esketamine. "
             "Classification comes from intervention names in the pipeline.")
    c1, c2 = st.columns(2)
    psy_year = (interventions[interventions["nct_id"].isin(psy["nct_id"])]
                .dropna(subset=["psychedelic_class"])
                .drop_duplicates(["nct_id", "psychedelic_class"])
                .merge(psy[["nct_id", "start_year"]], on="nct_id")
                .groupby(["start_year", "psychedelic_class"]).size().reset_index(name="trials"))
    psy_year["psychedelic_class"] = psy_year["psychedelic_class"].replace(
        {"Ketamine / esketamine": "Ketamine / Esketamine"})
    fig = px.bar(psy_year, x="start_year", y="trials", color="psychedelic_class",
                 labels={"start_year": "Year started", "trials": "Trials", "psychedelic_class": ""},
                 title="Psychedelic & Ketamine trials started each year")
    t.chart(c1, fig, alt="Stacked bar chart of psychedelic or MDMA and ketamine or esketamine trials "
                         "started each year.")

    psy_cond = (conditions[conditions["nct_id"].isin(psy["nct_id"])]
                .drop_duplicates(["nct_id", "condition_group"])
                .groupby("condition_group").size().sort_values().reset_index(name="trials"))
    fig = px.bar(psy_cond, x="trials", y="condition_group", orientation="h",
                 labels={"trials": "Trials", "condition_group": ""},
                 title="Conditions studied")
    t.chart(c2, fig, alt="Bar chart of psychedelic and ketamine trials by condition group.")

    top = psy.groupby("sponsor_name").size().nlargest(10).sort_values().reset_index(name="trials")
    fig = px.bar(top, x="trials", y="sponsor_name", orientation="h",
                 labels={"trials": "Trials", "sponsor_name": ""}, title="Top 10 Sponsors")
    t.chart(st, fig, alt="Bar chart of the ten sponsors with the most psychedelic and ketamine trials.")
