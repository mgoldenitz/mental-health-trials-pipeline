"""Overview page: trends by condition, treatment, sponsor and outcome, plus results posting."""
import plotly.express as px
import streamlit as st

import tracker as t

trials, conditions, interventions, sites = t.load_data()
view = t.filtered_view()
ids = set(view["nct_id"])
picked_groups = t.current_filters()["condition"]

if not view.empty:
    c1, c2 = st.columns(2)
    by_year = (conditions[conditions["nct_id"].isin(ids)]
               .merge(view[["nct_id", "start_year"]], on="nct_id")
               .drop_duplicates(["nct_id", "condition_group"])
               .groupby(["start_year", "condition_group"]).size().reset_index(name="trials"))
    if picked_groups:
        by_year = by_year[by_year["condition_group"].isin(picked_groups)]
    fig = px.line(by_year, x="start_year", y="trials", color="condition_group", markers=True,
                  color_discrete_map=t.group_colours(),
                  category_orders={"condition_group": t.by_last_value(by_year, "start_year", "trials",
                                                                      "condition_group")},
                  labels={"start_year": "Year started", "trials": "Trials", "condition_group": "Condition"},
                  title="Trials started each year, by Condition")
    t.chart(c1, fig, alt="Line chart of trials started each year from 2010 to 2025, one line per condition group.")

    treat = t.other_last(interventions[interventions["nct_id"].isin(ids)]
                         .drop_duplicates(["nct_id", "treatment_type"])
                         .groupby("treatment_type").size().reset_index(name="trials"), "treatment_type")
    fig = px.bar(treat, x="trials", y="treatment_type", orientation="h",
                 labels={"trials": "Trials", "treatment_type": ""},
                 title="Trials by Treatment type (a trial can test more than one)")
    t.chart(c2, fig)

    c3, c4 = st.columns(2)
    spons = t.other_last(view.groupby("sponsor_type").size().reset_index(name="trials"), "sponsor_type")
    fig = px.bar(spons, x="trials", y="sponsor_type", orientation="h",
                 labels={"trials": "Trials", "sponsor_type": ""}, title="Trials by Sponsor type")
    t.chart(c3, fig)

    outc = view.groupby("outcome").size().reset_index(name="trials")
    fig = px.bar(outc, x="trials", y="outcome", orientation="h", labels={"trials": "Trials", "outcome": ""},
                 category_orders={"outcome": t.OUTCOME_ORDER}, title="Trial Outcomes")
    t.chart(c4, fig)

# Results posting uses fixed published figures, so it shows even when the filters match nothing
st.subheader("Do completed trials post their results?")
st.caption("Completed trials in the published analysis whose primary completion date was on or before "
           "30 September 2025 (8,230 trials), so each had at least a year to post results on "
           "ClinicalTrials.gov before the download. US law requires results only for some trials, "
           "so these are reporting rates, not compliance rates. Groups with fewer than 30 trials are "
           "left out. The sidebar filters do not apply here.")
results = t.load_results()
rr = results[(results["sponsor_type"] != "All") & (results["completed_trials"] >= 30)]
allrow = results.query("sponsor_type == 'All'").set_index("us_site")
with st.grid(3, min_column_width=165, gap="small"):
    st.metric("Posted results", f"{allrow.loc['all', 'pct_with_results']:.0f}%",
              f"{int(allrow.loc['all', 'with_results']):,} of {int(allrow.loc['all', 'completed_trials']):,} trials",
              delta_color="off", delta_arrow="off")
    st.metric("With a US site", f"{allrow.loc['yes', 'pct_with_results']:.0f}%",
              f"{int(allrow.loc['yes', 'completed_trials']):,} trials", delta_color="off", delta_arrow="off")
    st.metric("Without a US site", f"{allrow.loc['no', 'pct_with_results']:.0f}%",
              f"{int(allrow.loc['no', 'completed_trials']):,} trials", delta_color="off", delta_arrow="off")

c5, c6 = st.columns(2)
by_sponsor = rr[rr["us_site"] == "all"].sort_values("pct_with_results")
fig = px.bar(by_sponsor, x="pct_with_results", y="sponsor_type", orientation="h",
             text=by_sponsor["pct_with_results"].round().astype(int).astype(str) + "%",
             hover_data={"completed_trials": ":,", "with_results": ":,"},
             labels={"pct_with_results": "Posted results (%)", "sponsor_type": "",
                     "completed_trials": "Completed trials", "with_results": "Posted results"},
             title="Share of completed trials that posted results, by Sponsor type")
fig.update_xaxes(range=[0, 100])
t.chart(c5, fig)

us_colours = t.us_site_colours()
by_site = rr[rr["us_site"] != "all"].copy()
by_site["US site"] = by_site["us_site"].map({"yes": "With a US site", "no": "Without a US site"})
order = by_sponsor["sponsor_type"].tolist()
fig = px.bar(by_site, x="pct_with_results", y="sponsor_type", color="US site", orientation="h",
             barmode="group", category_orders={"sponsor_type": order[::-1],
                                               "US site": ["With a US site", "Without a US site"]},
             color_discrete_map=us_colours,
             hover_data={"completed_trials": ":,", "with_results": ":,"},
             labels={"pct_with_results": "Posted results (%)", "sponsor_type": "",
                     "completed_trials": "Completed trials", "with_results": "Posted results"},
             title="With and without a US site")
fig.update_xaxes(range=[0, 100])
fig.update_layout(legend_title_text="")
# Outline the pale "without" bars in the strong blue so they stand out from the background
fig.update_traces(marker_line_color=us_colours["With a US site"], marker_line_width=1.5)
t.chart(c6, fig, alt="Grouped bar chart of the share of completed trials that posted results, "
                     "by sponsor type, for trials with and without a US site.")
