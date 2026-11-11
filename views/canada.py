"""Canada page: ClinicalTrials.gov trials with a Canadian site."""
import plotly.express as px
import streamlit as st

import tracker as t

trials, conditions, interventions, sites = t.load_data()
view = t.filtered_view()
ca = view[view["in_canada"]]
if ca.empty:
    st.info("No trials in Canada match the current filters.")
else:
    c1, c2 = st.columns(2)
    ca_cond = (conditions[conditions["nct_id"].isin(ca["nct_id"])]
               .drop_duplicates(["nct_id", "condition_group"])
               .groupby("condition_group").size().sort_values().reset_index(name="trials"))
    fig = px.bar(ca_cond, x="trials", y="condition_group", orientation="h",
                 labels={"trials": "Trials", "condition_group": ""},
                 title="Trials in Canada, by Condition")
    t.chart(c1, fig)

    top_countries = (sites[sites["nct_id"].isin(view["nct_id"])].drop_duplicates()
                     .groupby("country").size().nlargest(10).sort_values().reset_index(name="trials"))
    fig = px.bar(top_countries, x="trials", y="country", orientation="h",
                 labels={"trials": "Trials", "country": ""},
                 title="Top 10 Countries")
    t.chart(c2, fig, alt="Bar chart of the ten countries with the most trial sites among the filtered trials.")

    st.subheader("Recruiting in Canada now")
    rec = ca[ca["overall_status"] == "RECRUITING"].sort_values("start_year", ascending=False)
    if rec.empty:
        st.write("None match the current filters.")
    else:
        st.dataframe(
            rec[["link", "title", "conditions", "phase", "start_year", "sponsor_name"]],
            column_config={
                "link": st.column_config.LinkColumn("Trial", display_text=r"study/(NCT\d+)"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "conditions": "Condition", "phase": "Phase",
                "start_year": st.column_config.NumberColumn("Start", format="%d"),
                "sponsor_name": "Sponsor",
            },
            hide_index=True, width="stretch",
            alt="Table of trials recruiting at a Canadian site, newest first.")

st.caption("Trials authorized by Health Canada, including some not registered on ClinicalTrials.gov, "
           "are on the Health Canada page under Weekly updates.")
