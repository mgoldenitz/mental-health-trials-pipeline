"""
Mental Health & Psychedelic Trial Tracker (version 1)
Michael Goldenitz

A Streamlit app built on the cleaned outputs of the Mental Health Clinical
Trials Pipeline (data/powerbi). Run locally with:  streamlit run app.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data" / "powerbi"
CTGOV = "https://clinicaltrials.gov/study/"

# Readable phase names, in the order trials move through them
PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE1/PHASE2": "Phase 1/2",
    "PHASE2": "Phase 2",
    "PHASE2/PHASE3": "Phase 2/3",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
}
PHASE_ORDER = list(PHASE_LABELS.values()) + ["Not applicable"]

st.set_page_config(page_title="Mental Health Trial Tracker", page_icon="🧠", layout="wide")


# ---------------------------------------------------------------- data
@st.cache_data
def load_data():
    trials = pd.read_csv(DATA / "trials.csv")
    conditions = pd.read_csv(DATA / "conditions.csv")
    interventions = pd.read_csv(DATA / "interventions.csv")
    sites = pd.read_csv(DATA / "sites.csv")

    # One row per trial: condition groups, treatment types, psychedelic class, countries
    def joined(df, col):
        return (df.dropna(subset=[col]).groupby("nct_id")[col]
                  .agg(lambda s: ", ".join(sorted(s.unique()))))

    trials = trials.set_index("nct_id")
    trials["conditions"] = joined(conditions, "condition_group")
    trials["treatments"] = joined(interventions, "treatment_type")
    trials["psychedelic_class"] = joined(interventions, "psychedelic_class")
    trials["countries"] = joined(sites, "country")
    trials["in_canada"] = trials.index.isin(sites.loc[sites["country"] == "Canada", "nct_id"])
    trials["phase"] = trials["phase"].map(PHASE_LABELS).fillna("Not applicable")
    trials["status"] = trials["overall_status"].str.replace("_", " ").str.capitalize()
    trials["link"] = CTGOV + trials.index
    trials = trials.reset_index()

    return trials, conditions, interventions, sites


trials, conditions, interventions, sites = load_data()


# ---------------------------------------------------------------- sidebar filters
st.sidebar.title("Filters")

groups = sorted(conditions["condition_group"].dropna().unique())
pick_groups = st.sidebar.multiselect("Condition", groups, placeholder="All conditions")

treat_types = sorted(interventions["treatment_type"].dropna().unique())
pick_treat = st.sidebar.multiselect("Treatment type", treat_types, placeholder="All treatment types")

outcomes = sorted(trials["outcome"].dropna().unique())
pick_outcome = st.sidebar.multiselect("Outcome", outcomes, placeholder="All outcomes")

phases = [p for p in PHASE_ORDER if p in set(trials["phase"])]
pick_phase = st.sidebar.multiselect("Phase", phases, placeholder="All phases",
                                    help="Phase 1 tests safety in a small group, Phase 2 tests whether it works, "
                                         "Phase 3 confirms it in a large group, and Phase 4 follows it after approval. "
                                         "Combined phases (e.g. Phase 1/2) run two stages in one trial. "
                                         "Not applicable covers trials without drug phases, such as therapy or device studies.")

y_min, y_max = int(trials["start_year"].min()), int(trials["start_year"].max())
years = st.sidebar.slider("Start year", y_min, y_max, (y_min, y_max))

psy_only = st.sidebar.toggle("Psychedelic or ketamine trials only")
canada_only = st.sidebar.toggle("Trials in Canada")

st.sidebar.caption("Data: ClinicalTrials.gov, trials starting 2010–2025, "
                   "processed by the Mental Health Clinical Trials Pipeline.")


def apply_filters(df):
    mask = df["start_year"].between(*years)
    if pick_groups:
        ids = conditions.loc[conditions["condition_group"].isin(pick_groups), "nct_id"]
        mask &= df["nct_id"].isin(ids)
    if pick_treat:
        ids = interventions.loc[interventions["treatment_type"].isin(pick_treat), "nct_id"]
        mask &= df["nct_id"].isin(ids)
    if pick_outcome:
        mask &= df["outcome"].isin(pick_outcome)
    if pick_phase:
        mask &= df["phase"].isin(pick_phase)
    if psy_only:
        mask &= df["psychedelic_class"].notna()
    if canada_only:
        mask &= df["in_canada"]
    return df[mask]


view = apply_filters(trials)
ids = set(view["nct_id"])


# ---------------------------------------------------------------- header
st.title("Mental Health & Psychedelic Trial Tracker")
st.caption("Search and explore mental health clinical trials registered on ClinicalTrials.gov. "
           "Use the filters on the left; every chart and table updates with them.")

if view.empty:
    st.warning("No trials match these filters. Try removing one.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Trials", f"{len(view):,}")
k2.metric("Recruiting now", f"{(view['overall_status'] == 'RECRUITING').sum():,}")
k3.metric("Psychedelic or ketamine", f"{view['psychedelic_class'].notna().sum():,}")
k4.metric("In Canada", f"{view['in_canada'].sum():,}")

tab_overview, tab_search, tab_psy, tab_canada = st.tabs(
    ["Overview", "Find trials", "Psychedelics & ketamine", "Canada"])


# ---------------------------------------------------------------- overview
with tab_overview:
    c1, c2 = st.columns(2)

    by_year = (conditions[conditions["nct_id"].isin(ids)]
               .merge(view[["nct_id", "start_year"]], on="nct_id")
               .drop_duplicates(["nct_id", "condition_group"])
               .groupby(["start_year", "condition_group"]).size().reset_index(name="trials"))
    if pick_groups:
        by_year = by_year[by_year["condition_group"].isin(pick_groups)]
    fig = px.line(by_year, x="start_year", y="trials", color="condition_group", markers=True,
                  labels={"start_year": "Start year", "trials": "Trials", "condition_group": "Condition"},
                  title="Trial starts per year by condition")
    c1.plotly_chart(fig, width="stretch")

    treat = (interventions[interventions["nct_id"].isin(ids)]
             .drop_duplicates(["nct_id", "treatment_type"])
             .groupby("treatment_type").size().sort_values().reset_index(name="trials"))
    fig = px.bar(treat, x="trials", y="treatment_type", orientation="h",
                 labels={"trials": "Trials", "treatment_type": ""},
                 title="Trials by treatment type (a trial can test more than one)")
    c2.plotly_chart(fig, width="stretch")

    c3, c4 = st.columns(2)
    spons = view.groupby("sponsor_type").size().sort_values().reset_index(name="trials")
    fig = px.bar(spons, x="trials", y="sponsor_type", orientation="h",
                 labels={"trials": "Trials", "sponsor_type": ""}, title="Trials by sponsor type")
    c3.plotly_chart(fig, width="stretch")

    outc = view.groupby("outcome").size().reset_index(name="trials")
    fig = px.bar(outc, x="outcome", y="trials", labels={"trials": "Trials", "outcome": ""},
                 title="Trial outcomes")
    c4.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------- search
with tab_search:
    query = st.text_input("Search trial titles or sponsors", placeholder="e.g. psilocybin, CAMH, insomnia")
    table = view
    if query:
        q = query.strip()
        table = view[view["title"].str.contains(q, case=False, na=False)
                     | view["sponsor_name"].str.contains(q, case=False, na=False)]
    recruiting_first = st.checkbox("Show recruiting trials first", value=True)
    if recruiting_first:
        table = table.assign(_r=table["overall_status"].ne("RECRUITING")).sort_values(
            ["_r", "start_year"], ascending=[True, False])
    else:
        table = table.sort_values("start_year", ascending=False)

    st.write(f"{len(table):,} trials")
    st.dataframe(
        table[["link", "title", "conditions", "treatments", "phase", "status",
               "start_year", "enrollment", "sponsor_name", "countries"]],
        column_config={
            "link": st.column_config.LinkColumn("Trial", display_text=r"study/(NCT\d+)"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "conditions": "Condition",
            "treatments": "Treatment type",
            "phase": "Phase",
            "status": "Status",
            "start_year": st.column_config.NumberColumn("Start", format="%d"),
            "enrollment": st.column_config.NumberColumn("Enrolment", format="%d"),
            "sponsor_name": "Sponsor",
            "countries": "Countries",
        },
        hide_index=True, width="stretch", height=520,
    )
    st.download_button("Download these trials (CSV)",
                       table.drop(columns=["_r"], errors="ignore").to_csv(index=False),
                       file_name="trials_filtered.csv", mime="text/csv")


# ---------------------------------------------------------------- psychedelics
with tab_psy:
    psy = view[view["psychedelic_class"].notna()]
    if psy.empty:
        st.info("No psychedelic or ketamine trials match the current filters.")
    else:
        st.write("Trials testing a classic psychedelic or MDMA, or ketamine / esketamine. "
                 "Classification comes from intervention names in the pipeline.")
        c1, c2 = st.columns(2)
        psy_year = (interventions[interventions["nct_id"].isin(psy["nct_id"])]
                    .dropna(subset=["psychedelic_class"])
                    .drop_duplicates(["nct_id", "psychedelic_class"])
                    .merge(psy[["nct_id", "start_year"]], on="nct_id")
                    .groupby(["start_year", "psychedelic_class"]).size().reset_index(name="trials"))
        fig = px.bar(psy_year, x="start_year", y="trials", color="psychedelic_class",
                     labels={"start_year": "Start year", "trials": "Trials", "psychedelic_class": ""},
                     title="Psychedelic and ketamine trial starts per year")
        c1.plotly_chart(fig, width="stretch")

        psy_cond = (conditions[conditions["nct_id"].isin(psy["nct_id"])]
                    .drop_duplicates(["nct_id", "condition_group"])
                    .groupby("condition_group").size().sort_values().reset_index(name="trials"))
        fig = px.bar(psy_cond, x="trials", y="condition_group", orientation="h",
                     labels={"trials": "Trials", "condition_group": ""},
                     title="Conditions studied")
        c2.plotly_chart(fig, width="stretch")

        top = psy.groupby("sponsor_name").size().nlargest(10).sort_values().reset_index(name="trials")
        fig = px.bar(top, x="trials", y="sponsor_name", orientation="h",
                     labels={"trials": "Trials", "sponsor_name": ""}, title="Top 10 sponsors")
        st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------- canada
with tab_canada:
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
                     title="Trials in Canada, by condition")
        c1.plotly_chart(fig, width="stretch")

        countries = (sites[sites["nct_id"].isin(ids)].drop_duplicates()
                     .groupby("country").size().nlargest(10).sort_values().reset_index(name="trials"))
        fig = px.bar(countries, x="trials", y="country", orientation="h",
                     labels={"trials": "Trials", "country": ""},
                     title="Top 10 countries")
        c2.plotly_chart(fig, width="stretch")

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
                hide_index=True, width="stretch")
