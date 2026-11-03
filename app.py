"""
Mental Health & Psychedelic Trial Tracker (version 1)
Michael Goldenitz

A Streamlit app built on the cleaned outputs of the Mental Health Clinical
Trials Pipeline (data/powerbi). Run locally with:  streamlit run app.py
"""

from pathlib import Path
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data" / "powerbi"
BASELINE = Path(__file__).parent / "data" / "baseline" / "counts_2026-10-01.csv"
RESULTS = Path(__file__).parent / "results" / "10_results_reporting.csv"
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

# Outcome labels in sentence case, ordered from still running to finished
OUTCOME_LABELS = {
    "Ongoing or Unknown": "Ongoing or unknown",
    "Completed": "Completed",
    "Stopped Early": "Stopped early",
}
OUTCOME_ORDER = list(OUTCOME_LABELS.values())

# Old group names that can still appear in S3 files written before the November 2026 rename
RENAME = {"Schizophrenia & psychosis": "Schizophrenia & Psychosis"}


def relabel(series):
    """Condition group names as shown in the app (also inside comma-joined lists)."""
    out = series
    for old, new in RENAME.items():
        out = out.str.replace(old, new, regex=False)
    return out


# One fixed, dark colour per condition group, so a group keeps its colour when others are filtered out
GROUP_COLOURS = {
    "Anxiety": "#0072B2",
    "Bipolar disorder": "#B5397F",
    "Depression": "#D55E00",
    "Eating disorders": "#8C564B",
    "OCD": "#555555",
    "PTSD": "#009E73",
    "Schizophrenia & Psychosis": "#6A3D9A",
    "Substance use": "#A67C00",
}
NEW_GROUP_COLOURS = {
    "ADHD": "#0072B2",
    "Autism spectrum": "#D55E00",
    "Gambling & gaming disorders": "#009E73",
    "Personality disorders": "#6A3D9A",
}


def other_last(df, col):
    """Rows sorted smallest to largest, with "Other" first so it is drawn at the bottom of a
    horizontal bar chart instead of among the real categories."""
    df = df.sort_values("trials")
    return pd.concat([df[df[col] == "Other"], df[df[col] != "Other"]])


def by_last_value(df, x, y, group):
    """Group names ordered by their value in the latest year, highest first, so the
    legend lists the lines in the same order they end on the chart."""
    return df.sort_values(x).groupby(group)[y].last().sort_values(ascending=False).index.tolist()
    span = max(df[y].max() - df[y].min(), 1)
    gap = span / 22
    placed = []
    for row in ends.itertuples():
        pos = getattr(row, y)
        if placed and pos - placed[-1] < gap:
            pos = placed[-1] + gap
        placed.append(pos)
        fig.add_annotation(x=getattr(row, x), y=pos, text=getattr(row, group), showarrow=False,
                           xanchor="left", xshift=8, font=dict(color=colours.get(getattr(row, group), "#333"), size=12))
    first, last = int(df[x].min()), int(df[x].max())
    step = 5 if last - first >= 8 else 1
    fig.update_xaxes(range=[first - 0.5, last + (last - first) * 0.65 + 1],
                     tickvals=list(range(first, last + 1, step)))
    fig.update_layout(showlegend=False)
    return fig

st.set_page_config(page_title="Mental Health & Psychedelic Trial Tracker", layout="wide")


# ---------------------------------------------------------------- data
@st.cache_data
def load_data():
    trials = pd.read_csv(DATA / "trials.csv")
    conditions = pd.read_csv(DATA / "conditions.csv")
    interventions = pd.read_csv(DATA / "interventions.csv")
    sites = pd.read_csv(DATA / "sites.csv")
    conditions["condition_group"] = relabel(conditions["condition_group"])

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
    trials["outcome"] = trials["outcome"].map(OUTCOME_LABELS).fillna(trials["outcome"])
    trials["link"] = CTGOV + trials.index
    trials = trials.reset_index()

    return trials, conditions, interventions, sites


def aws_secrets():
    """The [aws] block of the app's secrets, or None if it has none."""
    try:
        return dict(st.secrets["aws"])
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600)
def load_weekly_search_data(cfg):
    """Load the latest S3 Parquet tables, limited to the eight published groups."""
    import io
    import json
    import boto3

    s3 = boto3.client("s3", aws_access_key_id=cfg["access_key_id"],
                      aws_secret_access_key=cfg["secret_access_key"], region_name=cfg["region"])

    def read(key):
        return s3.get_object(Bucket=cfg["bucket"], Key=key)["Body"].read()

    tables = {
        name: pd.read_parquet(io.BytesIO(read(f"athena/latest/{name}/{name}.parquet")))
        for name in ("trials", "conditions", "interventions", "sites")
    }
    manifest = json.loads(read("latest/manifest.json"))
    core_ids = set(tables["trials"].loc[tables["trials"]["scope"] == "core", "nct_id"])
    if not core_ids:
        raise ValueError("The weekly snapshot contains no trials in the published scope")

    trials = tables["trials"].loc[tables["trials"]["nct_id"].isin(core_ids)].copy()
    conditions = tables["conditions"].copy()
    conditions["condition_group"] = relabel(conditions["condition_group"])
    conditions = conditions.loc[
        conditions["nct_id"].isin(core_ids)
        & conditions["condition_group"].isin(GROUP_COLOURS)
    ].copy()
    interventions = tables["interventions"].loc[
        tables["interventions"]["nct_id"].isin(core_ids)
    ].copy()
    sites = tables["sites"].loc[tables["sites"]["nct_id"].isin(core_ids)].copy()

    def joined(df, col):
        return (df.dropna(subset=[col]).groupby("nct_id")[col]
                  .agg(lambda s: ", ".join(sorted(s.unique())))
                  )

    trials = trials.set_index("nct_id")
    trials["conditions"] = joined(conditions, "condition_group")
    trials["treatments"] = joined(interventions, "treatment_type")
    trials["psychedelic_class"] = joined(interventions, "psychedelic_class")
    trials["countries"] = joined(sites, "country")
    trials["in_canada"] = trials.index.isin(sites.loc[sites["country"] == "Canada", "nct_id"])
    trials["phase"] = trials["phase"].map(PHASE_LABELS).fillna("Not applicable")
    trials["status"] = trials["overall_status"].str.replace("_", " ").str.capitalize()
    trials["outcome"] = trials["outcome"].map(OUTCOME_LABELS).fillna(trials["outcome"])
    trials["link"] = CTGOV + trials.index
    return trials.reset_index(), conditions, interventions, sites, manifest


@st.cache_data(ttl=6 * 3600, max_entries=256)
def load_trial_details(nct_id):
    """Fetch one current ClinicalTrials.gov record by its NCT identifier."""
    if not re.fullmatch(r"NCT\d{8}", nct_id):
        raise ValueError("Invalid ClinicalTrials.gov identifier")
    request = Request(
        f"https://clinicaltrials.gov/api/v2/studies/{nct_id}",
        headers={"User-Agent": "MentalHealthTrialTracker/1.0"},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def detail_text(value):
    """Return a displayable string for an optional registry text field."""
    return value.strip() if isinstance(value, str) and value.strip() else "Not reported."


def show_trial_details(nct_id):
    """Render the selected registry record, with contact details left at the source."""
    try:
        record = load_trial_details(nct_id)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
        st.warning(
            "Trial details could not be loaded right now. Open the ClinicalTrials.gov record to view the latest information."
        )
        return

    protocol = record.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    description = protocol.get("descriptionModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    interventions_module = protocol.get("armsInterventionsModule", {})
    outcomes_module = protocol.get("outcomesModule", {})

    with st.container(border=True):
        st.subheader(ident.get("briefTitle") or nct_id)
        verified = status.get("statusVerifiedDate")
        status_text = status.get("overallStatus", "Status not reported").replace("_", " ").title()
        st.caption(f"{nct_id} · {status_text}" + (f" · Last verified {verified}" if verified else ""))
        st.link_button("View full record and contact details on ClinicalTrials.gov", f"{CTGOV}{nct_id}")

        summary = description.get("briefSummary")
        st.markdown("**Summary**")
        st.markdown(detail_text(summary))
        detailed = description.get("detailedDescription")
        if detailed:
            with st.expander("Detailed description"):
                st.markdown(detailed)

        st.markdown("**Interventions and dosage details reported**")
        interventions_list = interventions_module.get("interventions", [])
        if interventions_list:
            for item in interventions_list:
                name = item.get("name") or "Intervention name not reported"
                kind = item.get("type")
                st.markdown(f"- **{name}**" + (f" ({kind})" if kind else ""))
                if item.get("description"):
                    st.caption(item["description"])
        else:
            st.write("Not reported.")

        st.markdown("**Eligibility**")
        age = " to ".join(filter(None, [eligibility.get("minimumAge"), eligibility.get("maximumAge")]))
        eligibility_facts = [
            f"Age: {age}" if age else None,
            f"Sex: {eligibility.get('sex')}" if eligibility.get("sex") else None,
            "Accepts healthy volunteers: " + str(eligibility["healthyVolunteers"])
            if "healthyVolunteers" in eligibility else None,
        ]
        facts = [fact for fact in eligibility_facts if fact]
        if facts:
            st.caption(" · ".join(facts))
        st.markdown(detail_text(eligibility.get("eligibilityCriteria")))

        st.markdown("**Outcomes**")
        outcome_sections = [
            ("Primary", outcomes_module.get("primaryOutcomes", [])),
            ("Secondary", outcomes_module.get("secondaryOutcomes", [])),
            ("Other", outcomes_module.get("otherOutcomes", [])),
        ]
        reported_outcomes = False
        for label, items in outcome_sections:
            for item in items:
                reported_outcomes = True
                measure = item.get("measure") or "Outcome measure not reported"
                st.markdown(f"- **{label}: {measure}**")
                if item.get("description"):
                    st.caption(item["description"])
                if item.get("timeFrame"):
                    st.caption(f"Time frame: {item['timeFrame']}")
        if not reported_outcomes:
            st.write("Not reported.")


trials, conditions, interventions, sites = load_data()
weekly_trials = weekly_conditions = weekly_interventions = weekly_sites = weekly_manifest = None
weekly_data_error = False
weekly_cfg = aws_secrets()
if weekly_cfg:
    try:
        (weekly_trials, weekly_conditions, weekly_interventions,
         weekly_sites, weekly_manifest) = load_weekly_search_data(weekly_cfg)
    except Exception:
        weekly_data_error = True


# ---------------------------------------------------------------- sidebar filters
st.sidebar.title("Filters")

groups = sorted(conditions["condition_group"].dropna().unique())
treat_types = sorted(interventions["treatment_type"].dropna().unique())
outcomes = [o for o in OUTCOME_ORDER if o in set(trials["outcome"])]
phases = [p for p in PHASE_ORDER if p in set(trials["phase"])]
y_min, y_max = int(trials["start_year"].min()), int(trials["start_year"].max())
statuses = sorted(trials["status"].dropna().unique())
countries = sorted(sites["country"].dropna().unique())
if weekly_trials is not None:
    statuses = sorted(set(statuses) | set(weekly_trials["status"].dropna().unique()))
    countries = sorted(set(countries) | set(weekly_sites["country"].dropna().unique()))
pick_groups = st.sidebar.multiselect("Condition", groups, placeholder="All conditions",
                                     key="condition", bind="query-params")
pick_treat = st.sidebar.multiselect("Treatment type", treat_types, placeholder="All treatment types",
                                    key="treatment", bind="query-params")
pick_outcome = st.sidebar.multiselect(
    "Outcome", outcomes, placeholder="All outcomes",
    help="Ongoing or unknown covers trials still recruiting or running, "
         "plus trials whose status hasn't been updated in two years. "
         "Completed trials finished as planned. Stopped early covers "
         "trials that were terminated, suspended or withdrawn.",
    key="outcome", bind="query-params")
pick_phase = st.sidebar.multiselect(
    "Phase", phases, placeholder="All phases",
    help="Phase 1 tests safety in a small group, Phase 2 tests whether it works, "
         "Phase 3 confirms it in a large group, and Phase 4 follows it after approval. "
         "Combined phases (e.g. Phase 1/2) run two stages in one trial. "
         "Not applicable covers trials without drug phases, such as therapy or device studies.",
    key="phase", bind="query-params")
years = st.sidebar.slider("Year started", y_min, y_max, (y_min, y_max),
                          key="years", bind="query-params")
pick_status = st.sidebar.multiselect("Recruitment status", statuses, placeholder="All statuses",
                                     key="status", bind="query-params")
pick_country = st.sidebar.multiselect("Country", countries, placeholder="All countries",
                                      key="country", bind="query-params")
psy_only = st.sidebar.toggle("Psychedelic & Ketamine trials only",
                             key="psychedelic", bind="query-params")
canada_only = st.sidebar.toggle("Trials in Canada", key="canada", bind="query-params")

if weekly_trials is not None:
    st.sidebar.caption(
        f"Overview, psychedelic and Canada summary figures use the 1 October 2026 download. "
        f"Find trials uses the {weekly_manifest['snapshot_date']} weekly refresh, limited to the eight published groups."
    )
elif weekly_data_error:
    st.sidebar.warning("Weekly trial data is unavailable; Find trials is showing the 1 October 2026 snapshot.")
else:
    st.sidebar.caption(
        "Data: ClinicalTrials.gov, downloaded 1 October 2026. The weekly Find trials feed is not connected, "
        "so it is showing the published snapshot."
    )


def apply_filters(df, filter_conditions=None, filter_interventions=None, filter_sites=None):
    filter_conditions = conditions if filter_conditions is None else filter_conditions
    filter_interventions = interventions if filter_interventions is None else filter_interventions
    filter_sites = sites if filter_sites is None else filter_sites
    mask = df["start_year"].between(*years)
    if pick_groups:
        ids = filter_conditions.loc[filter_conditions["condition_group"].isin(pick_groups), "nct_id"]
        mask &= df["nct_id"].isin(ids)
    if pick_treat:
        ids = filter_interventions.loc[filter_interventions["treatment_type"].isin(pick_treat), "nct_id"]
        mask &= df["nct_id"].isin(ids)
    if pick_outcome:
        mask &= df["outcome"].isin(pick_outcome)
    if pick_phase:
        mask &= df["phase"].isin(pick_phase)
    if pick_status:
        mask &= df["status"].isin(pick_status)
    if pick_country:
        ids = filter_sites.loc[filter_sites["country"].isin(pick_country), "nct_id"]
        mask &= df["nct_id"].isin(ids)
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



def share(part, whole, text):
    return f"{part / whole:.1%} {text}" if whole else None


n_view = len(view)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Trials", f"{n_view:,}",
          share(n_view, len(trials), f"of all {len(trials):,}") if n_view < len(trials) else None,
          delta_color="off", delta_arrow="off")
for col, label, count in [
        (k2, "Recruiting now", int((view["overall_status"] == "RECRUITING").sum())),
        (k3, "Psychedelic & Ketamine", int(view["psychedelic_class"].notna().sum())),
        (k4, "In Canada", int(view["in_canada"].sum()))]:
    col.metric(label, f"{count:,}", share(count, n_view, "of trials"), delta_color="off", delta_arrow="off")

tab_overview, tab_search, tab_psy, tab_canada, tab_about, tab_new, tab_latest = st.tabs(
    ["Overview", "Find trials", "Psychedelic & Ketamine", "Canada", "About the data",
     "New groups (updated weekly)", "Latest refresh"])


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
                  color_discrete_map=GROUP_COLOURS,
                  category_orders={"condition_group": by_last_value(by_year, "start_year", "trials",
                                                                    "condition_group")},
                  labels={"start_year": "Year started", "trials": "Trials", "condition_group": "Condition"},
                  title="Trials started each year, by Condition")
    c1.plotly_chart(fig, width="stretch")

    treat = other_last(interventions[interventions["nct_id"].isin(ids)]
                       .drop_duplicates(["nct_id", "treatment_type"])
                       .groupby("treatment_type").size().reset_index(name="trials"), "treatment_type")
    fig = px.bar(treat, x="trials", y="treatment_type", orientation="h",
                 labels={"trials": "Trials", "treatment_type": ""},
                 title="Trials by Treatment type (a trial can test more than one)")
    c2.plotly_chart(fig, width="stretch")

    c3, c4 = st.columns(2)
    spons = other_last(view.groupby("sponsor_type").size().reset_index(name="trials"), "sponsor_type")
    fig = px.bar(spons, x="trials", y="sponsor_type", orientation="h",
                 labels={"trials": "Trials", "sponsor_type": ""}, title="Trials by Sponsor type")
    c3.plotly_chart(fig, width="stretch")

    outc = view.groupby("outcome").size().reset_index(name="trials")
    fig = px.bar(outc, x="trials", y="outcome", orientation="h", labels={"trials": "Trials", "outcome": ""},
                 category_orders={"outcome": OUTCOME_ORDER}, title="Trial Outcomes")
    c4.plotly_chart(fig, width="stretch")

    st.subheader("Do completed trials post their results?")
    st.caption("Completed trials in the published analysis whose primary completion date was on or before "
               "30 September 2025 (8,230 trials), so each had at least a year to post results on "
               "ClinicalTrials.gov before the download. US law requires results only for some trials, "
               "so these are reporting rates, not compliance rates. Groups with fewer than 30 trials are "
               "left out. The sidebar filters do not apply here.")
    rr = pd.read_csv(RESULTS)
    rr = rr[(rr["sponsor_type"] != "All") & (rr["completed_trials"] >= 30)]
    allrow = pd.read_csv(RESULTS).query("sponsor_type == 'All'").set_index("us_site")
    r1, r2, r3 = st.columns(3)
    r1.metric("Posted results", f"{allrow.loc['all', 'pct_with_results']:.0f}%",
              f"{int(allrow.loc['all', 'with_results']):,} of {int(allrow.loc['all', 'completed_trials']):,} trials",
              delta_color="off", delta_arrow="off")
    r2.metric("With a US site", f"{allrow.loc['yes', 'pct_with_results']:.0f}%",
              f"{int(allrow.loc['yes', 'completed_trials']):,} trials", delta_color="off", delta_arrow="off")
    r3.metric("Without a US site", f"{allrow.loc['no', 'pct_with_results']:.0f}%",
              f"{int(allrow.loc['no', 'completed_trials']):,} trials", delta_color="off", delta_arrow="off")

    c5, c6 = st.columns(2)
    by_sponsor = rr[rr["us_site"] == "all"].sort_values("pct_with_results")
    fig = px.bar(by_sponsor, x="pct_with_results", y="sponsor_type", orientation="h",
                 text=by_sponsor["pct_with_results"].round().astype(int).astype(str) + "%",
                 hover_data={"completed_trials": ":,", "with_results": ":,"},
                 labels={"pct_with_results": "Posted results (%)", "sponsor_type": "",
                         "completed_trials": "Completed trials", "with_results": "Posted results"},
                 title="Share of completed trials that posted results, by sponsor type")
    fig.update_xaxes(range=[0, 100])
    c5.plotly_chart(fig, width="stretch")

    by_site = rr[rr["us_site"] != "all"].copy()
    by_site["US site"] = by_site["us_site"].map({"yes": "With a US site", "no": "Without a US site"})
    order = by_sponsor["sponsor_type"].tolist()
    fig = px.bar(by_site, x="pct_with_results", y="sponsor_type", color="US site", orientation="h",
                 barmode="group", category_orders={"sponsor_type": order[::-1],
                                                   "US site": ["With a US site", "Without a US site"]},
                 color_discrete_map={"With a US site": "#0072B2", "Without a US site": "#9DB9D3"},
                 hover_data={"completed_trials": ":,", "with_results": ":,"},
                 labels={"pct_with_results": "Posted results (%)", "sponsor_type": "",
                         "completed_trials": "Completed trials", "with_results": "Posted results"},
                 title="With and without a US site")
    fig.update_xaxes(range=[0, 100])
    fig.update_layout(legend_title_text="")
    c6.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------- search
with tab_search:
    query = st.text_input("Search trial titles, sponsors or interventions",
                          placeholder="e.g. psilocybin, sertraline, CAMH",
                          key="q", bind="query-params")
    if weekly_trials is None:
        search_trials, search_conditions = trials, conditions
        search_interventions, search_sites = interventions, sites
        weekly_date = None
    else:
        search_trials, search_conditions = weekly_trials, weekly_conditions
        search_interventions, search_sites = weekly_interventions, weekly_sites
        weekly_date = weekly_manifest["snapshot_date"]
    search_view = apply_filters(search_trials, search_conditions, search_interventions, search_sites)
    table = search_view
    if query:
        q = query.strip()
        intervention_ids = search_interventions.loc[
            search_interventions["intervention_name"].str.contains(q, case=False, na=False, regex=False), "nct_id"]
        table = search_view[search_view["title"].str.contains(q, case=False, na=False, regex=False)
                            | search_view["sponsor_name"].str.contains(q, case=False, na=False, regex=False)
                            | search_view["nct_id"].isin(intervention_ids)]
    can_recruit = ((not pick_outcome or "Ongoing or unknown" in pick_outcome)
                   and (not pick_status or "Recruiting" in pick_status))
    recruiting_first = st.checkbox(
        "Show trials that are actively recruiting first", value=True, disabled=not can_recruit,
        help=None if can_recruit else
        "Recruiting trials are hidden by the Outcome or Recruitment status filter. Include "
        "\"Ongoing or unknown\" and \"Recruiting\" to use this.")
    recruiting_first = recruiting_first and can_recruit
    if recruiting_first:
        table = table.assign(_r=table["overall_status"].ne("RECRUITING")).sort_values(
            ["_r", "start_year"], ascending=[True, False])
    else:
        table = table.sort_values("start_year", ascending=False)

    st.write(f"{len(table):,} trials")
    if weekly_date:
        st.caption(f"Latest weekly refresh: {weekly_date}. Showing the published eight condition groups only.")
    else:
        st.caption("Showing the published 1 October 2026 snapshot; weekly data is unavailable.")
    result_table = table[["nct_id", "link", "title", "conditions", "treatments", "phase", "status",
                          "start_year", "enrollment", "sponsor_name", "countries"]].reset_index(drop=True)
    result_key = f"trial_results_{hash(tuple(result_table['nct_id']))}"
    st.caption("Select a trial row to view its current registry details.")
    selection = st.dataframe(
        result_table,
        column_config={
            "nct_id": None,
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
        on_select="rerun", selection_mode="single-row", key=result_key,
    )
    selected_rows = selection.selection.rows
    if selected_rows:
        selected_nct = result_table.iloc[selected_rows[0]]["nct_id"]
        show_trial_details(selected_nct)
    st.download_button("Download these trials (CSV)",
                       table.drop(columns=["_r"], errors="ignore").to_csv(index=False),
                       file_name="trials_filtered.csv", mime="text/csv")


# ---------------------------------------------------------------- psychedelics
with tab_psy:
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
        fig = px.bar(psy_year, x="start_year", y="trials", color="psychedelic_class",
                     labels={"start_year": "Year started", "trials": "Trials", "psychedelic_class": ""},
                     title="Psychedelic & Ketamine trials started each year")
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
                     labels={"trials": "Trials", "sponsor_name": ""}, title="Top 10 Sponsors")
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
                     title="Trials in Canada, by Condition")
        c1.plotly_chart(fig, width="stretch")

        countries = (sites[sites["nct_id"].isin(ids)].drop_duplicates()
                     .groupby("country").size().nlargest(10).sort_values().reset_index(name="trials"))
        fig = px.bar(countries, x="trials", y="country", orientation="h",
                     labels={"trials": "Trials", "country": ""},
                     title="Top 10 Countries")
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


# ---------------------------------------------------------------- latest refresh
# Takes the secrets as an argument so a missing-secrets result is never cached.
@st.cache_data(ttl=6 * 3600)
def load_refresh(cfg):
    """Counts from the newest weekly download in S3."""
    import io
    import json
    import boto3

    s3 = boto3.client("s3", aws_access_key_id=cfg["access_key_id"],
                      aws_secret_access_key=cfg["secret_access_key"], region_name=cfg["region"])

    def read(key):
        return s3.get_object(Bucket=cfg["bucket"], Key=key)["Body"].read()

    latest = pd.read_csv(io.BytesIO(read("latest/counts.csv")))
    manifest = json.loads(read("latest/manifest.json"))
    history = pd.read_csv(io.BytesIO(read("history/counts.csv")))
    return latest, manifest, history


# Takes the secrets as an argument so a missing-secrets result is never cached.
@st.cache_data(ttl=6 * 3600)
def load_health_canada(cfg):
    """Counts and the trial list from the newest weekly Health Canada download in S3."""
    import io
    import json
    import boto3

    s3 = boto3.client("s3", aws_access_key_id=cfg["access_key_id"],
                      aws_secret_access_key=cfg["secret_access_key"], region_name=cfg["region"])

    def read(key):
        return s3.get_object(Bucket=cfg["bucket"], Key="health-canada/" + key)["Body"].read()

    counts = pd.read_csv(io.BytesIO(read("latest/counts.csv")))
    manifest = json.loads(read("latest/manifest.json"))
    try:    # written from the 2026-11-02 run onward
        trials = pd.read_csv(io.BytesIO(read("latest/hc_trials.csv")), dtype={"control_number": str})
    except Exception:
        trials = None
    return counts, manifest, trials


with tab_canada:
    st.divider()
    st.subheader("Trials authorized by Health Canada")
    cfg = aws_secrets()
    try:
        hc = load_health_canada(cfg) if cfg else None
    except Exception as e:
        hc = False
        st.error(f"Could not read the Health Canada data from S3: {e}")
    if hc is None:
        st.info("This section shows mental health trials authorized by Health Canada. "
                "The scheduled refresh is not connected yet.")
    elif hc:
        hc_counts, hc_manifest, hc_trials = hc
        st.caption(
            f"Health Canada Clinical Trials Database, downloaded {hc_manifest['snapshot_date']}. "
            "It lists drug and biologic trials authorized by Health Canada since April 2013, including "
            "trials not registered on ClinicalTrials.gov. A trial counts when any of its conditions "
            "falls in one of the eight mental health groups. The sidebar filters do not apply here.")
        st.caption("Health Canada trial counts overlap with the ‘In Canada’ ClinicalTrials.gov count above; "
                   "do not add the two counts together.")

        def hc_metric(metric):
            out = hc_counts[hc_counts["metric"] == metric][["category", "value"]].copy()
            out["category"] = relabel(out["category"].astype(str))
            return out

        def hc_one(metric, category="All"):
            row = hc_counts[(hc_counts["metric"] == metric) & (hc_counts["category"] == category)]
            return int(row["value"].iloc[0]) if len(row) else 0

        status = hc_metric("hc_trials_by_status").set_index("category")["value"]
        drug = hc_metric("hc_trials_by_drug_class")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Mental health trials", f"{hc_one('hc_trials'):,}")
        k2.metric("All authorized trials", f"{hc_one('hc_all_trials'):,}")
        k3.metric("Ongoing", f"{int(status.get('Ongoing', 0)):,}")
        k4.metric("Psychedelic & Ketamine", f"{int(drug['value'].sum()):,}")

        c1, c2 = st.columns(2)
        by_cond = hc_metric("hc_trials_by_condition").sort_values("value")
        fig = px.bar(by_cond, x="value", y="category", orientation="h",
                     labels={"value": "Trials", "category": ""},
                     title="Health Canada trials, by condition")
        c1.plotly_chart(fig, width="stretch")
        by_year = hc_metric("hc_trials_by_year").copy()
        by_year["category"] = pd.to_numeric(by_year["category"], errors="coerce")
        fig = px.bar(by_year.dropna(), x="category", y="value",
                     labels={"category": "Year approved", "value": "Trials"},
                     title="Health Canada trials, by year approved")
        c2.plotly_chart(fig, width="stretch")

        if hc_trials is not None:
            st.markdown("Ongoing Health Canada trials")
            ongoing = (hc_trials[hc_trials["status"] == "Ongoing"]
                       .sort_values("approved_date", ascending=False)
                       .assign(condition_group=lambda d: relabel(d["condition_group"].fillna(""))))
            st.dataframe(
                ongoing[["control_number", "title", "condition_group", "approved_date",
                         "sponsor_name", "psychedelic_class"]],
                column_config={
                    "control_number": "Control number",
                    "title": st.column_config.TextColumn("Title", width="large"),
                    "condition_group": "Condition", "approved_date": "Approved",
                    "sponsor_name": "Sponsor", "psychedelic_class": "Drug class",
                },
                hide_index=True, width="stretch")


with tab_about:
    st.subheader("About the data")
    st.markdown(
        "The **Overview**, **Psychedelic & Ketamine**, and ClinicalTrials.gov figures on the **Canada** tab "
        "use the published 1 October 2026 download. **Find trials** uses the latest weekly refresh so its "
        "recruitment statuses stay current, while keeping only trials in the eight published condition groups. "
        "The **New groups** and **Latest refresh** tabs show separate weekly data and do not change published totals.")

    st.markdown("**Source and published scope**")
    st.markdown(
        "The source is the ClinicalTrials.gov API v2. The download contains 18,357 interventional "
        "studies. The published analysis includes 14,724 (80%) that started between 2010 and 2025 "
        "and list at least one of eight project-defined condition groups: depression, anxiety, OCD, "
        "PTSD, bipolar disorder, schizophrenia and psychosis, substance use, and eating disorders.")

    st.markdown("**How conditions are grouped**")
    st.markdown(
        "ClinicalTrials.gov condition names are free text. Project keyword rules exclude known "
        "non-psychiatric uses first, then assign each condition to the first matching group. A trial "
        "may list several conditions and belong to several groups, so group counts can add up to more "
        "than the total number of trials.")

    st.markdown("**What is outside the published analysis**")
    st.markdown(
        "The condition search was not designed to capture every mental or neurological condition. "
        "For example, ADHD, autism, dementia, pain, insomnia, and studies of healthy volunteers are "
        "not included unless a trial also lists one of the eight grouped conditions. The four newer "
        "groups are presented separately in **New groups**.")

    st.markdown("**How to interpret the numbers**")
    st.markdown(
        "These figures describe registered research activity; more trials do not mean better or more "
        "effective treatments. ClinicalTrials.gov is US-based, and many trials elsewhere are recorded "
        "in other registries. Since overall registration grew during this period, comparisons between "
        "groups are more informative than raw growth alone.")
    st.markdown(
        "Results-posting figures are reporting rates, not compliance rates. Legal reporting rules apply "
        "only to some trials, and this analysis does not determine which trials were legally required "
        "to report results.")


def compare(baseline, latest, metric):
    """Published and latest values of one metric side by side."""
    b = baseline[baseline["metric"] == metric].assign(category=lambda d: relabel(d["category"]))
    l = latest[latest["metric"] == metric].assign(category=lambda d: relabel(d["category"]))
    b, l = b.set_index("category")["value"], l.set_index("category")["value"]
    out = pd.DataFrame({"Published": b, "Latest": l}).fillna(0).astype(int)
    out["Change"] = out["Latest"] - out["Published"]
    out.index.name = None
    return out


with tab_latest:
    cfg = aws_secrets()
    try:
        refresh = load_refresh(cfg) if cfg else None
    except Exception as e:
        refresh = False
        st.error(f"Could not read the latest refresh from S3: {e}")
    if refresh is None:
        st.info("This tab shows counts from the latest weekly download next to the published "
                "counts from 1 October 2026. The scheduled refresh is not connected yet.")
    elif refresh:
        latest, manifest, history = refresh
        baseline = pd.read_csv(BASELINE)
        st.caption(f"Latest download: {manifest['snapshot_date']}. Published analysis: 1 October 2026. "
                   "Both count trials that began between 2010 and 2025, so a change means records were added, "
                   "removed or edited in the registry. The sidebar filters do not apply to this tab.")

        def one(df, metric, category="All"):
            row = df[(df["metric"] == metric) & (df["category"] == category)]
            return int(row["value"].iloc[0]) if len(row) else 0

        k1, k2, k3, k4 = st.columns(4)
        for col, label, metric, category in [
                (k1, "Trials", "trials", "All"),
                (k2, "Psychedelic / MDMA", "trials_by_drug_class", "Psychedelic / MDMA"),
                (k3, "Ketamine / Esketamine", "trials_by_drug_class", "Ketamine / esketamine"),
                (k4, "With a Canadian site", "trials_with_canadian_site", "All")]:
            now, then = one(latest, metric, category), one(baseline, metric, category)
            col.metric(label, f"{now:,}", f"{now - then:+,} since publication", delta_color="off")

        c1, c2 = st.columns(2)
        by_year = compare(baseline, latest, "trials_by_year").reset_index(names="start_year")
        by_year["start_year"] = by_year["start_year"].astype(int)
        fig = px.line(by_year.melt(id_vars="start_year", value_vars=["Published", "Latest"]),
                      x="start_year", y="value", color="variable", markers=True,
                      labels={"start_year": "Year started", "value": "Trials", "variable": ""},
                      title="Trials started each year")
        c1.plotly_chart(fig, width="stretch")

        c2.markdown("Trials by condition")
        c2.dataframe(compare(baseline, latest, "trials_by_condition"), width="stretch")
        c2.markdown("Trials by outcome")
        c2.dataframe(compare(baseline, latest, "trials_by_outcome"), width="stretch")

        later = latest[latest["metric"] == "started_after_window"]
        if len(later):
            st.write("Trials with a start date after 2025 (outside the published analysis): " +
                     ", ".join(f"{r.category}: {r.value:,}" for r in later.itertuples()) +
                     ". Many of these start dates are still estimates.")

        st.caption("The four condition groups added in November 2026 are on the New groups tab.")

        totals = history[(history["metric"] == "trials") & (history["category"] == "All")].copy()
        totals["snapshot_date"] = pd.to_datetime(totals["snapshot_date"])
        totals = (totals.sort_values("snapshot_date")
                  .drop_duplicates("snapshot_date", keep="last"))
        if len(totals) >= 4:
            fig = px.line(totals, x="snapshot_date", y="value", markers=True,
                          labels={"snapshot_date": "Download date", "value": "Trials that began 2010–2025"},
                          title="Trials in the analysis window at each weekly download")
            fig.update_xaxes(tickformat="%b %d, %Y",
                             tickvals=totals["snapshot_date"] if len(totals) <= 12 else None)
            fig.update_yaxes(tickformat=",d", dtick=max(1, round((totals["value"].max()
                                                                  - totals["value"].min()) / 5)))
            st.plotly_chart(fig, width="stretch")
        elif len(totals):
            last = totals.iloc[-1]
            when = f"{last.snapshot_date:%b} {last.snapshot_date.day}"
            text = f"{int(last.value):,} trials in the 2010–2025 window at the {when} download"
            if len(totals) > 1:
                prev = totals.iloc[-2]
                diff = int(last.value - prev.value)
                since = f"{prev.snapshot_date:%b} {prev.snapshot_date.day}"
                text += (f", no change from {since}" if diff == 0
                         else f", {diff:+,} from {since}")
            st.write(text + ". A weekly chart appears here once there are four downloads.")


with tab_new:
    cfg = aws_secrets()
    try:
        refresh = load_refresh(cfg) if cfg else None
    except Exception as e:
        refresh = False
        st.error(f"Could not read the latest refresh from S3: {e}")
    if refresh is None:
        st.info("This tab shows ADHD, autism spectrum, personality disorder and gambling or gaming "
                "trials from the weekly download. The scheduled refresh is not connected yet.")
    elif refresh:
        latest, manifest, _ = refresh
        new = latest[latest["metric"] == "v2_trials_by_new_condition"]
        if new.empty:
            st.info("The latest weekly download does not include the new condition groups yet.")
        else:
            st.markdown(f"**Updated weekly.** Latest download: {manifest['snapshot_date']}.")
            st.caption("These four groups come from a second ClinicalTrials.gov search added in November 2026. "
                       "They are not part of the published analysis of 1 October 2026, so the counts on the "
                       "other tabs do not include them, and these numbers change every Monday. Trials that "
                       "began between 2010 and 2025. A trial can be in more than one group, including a "
                       "published one. The sidebar filters do not apply here.")

            def one_new(metric, category="All"):
                row = latest[(latest["metric"] == metric) & (latest["category"] == category)]
                return int(row["value"].iloc[0]) if len(row) else 0

            counts_new = new.set_index("category")["value"].astype(int)
            cols = st.columns(len(counts_new))
            for col, (grp, n) in zip(cols, counts_new.sort_values(ascending=False).items()):
                col.metric(grp, f"{n:,}")

            c1, c2 = st.columns(2)
            yearly = latest[latest["metric"] == "v2_trials_by_new_condition_year"].copy()
            if len(yearly):
                yearly[["group", "start_year"]] = yearly["category"].str.split("|", n=1, expand=True)
                yearly["start_year"] = pd.to_numeric(yearly["start_year"], errors="coerce")
                yearly = yearly.dropna(subset=["start_year"]).rename(columns={"value": "trials"})
                fig = px.line(yearly, x="start_year", y="trials", color="group", markers=True,
                              color_discrete_map=NEW_GROUP_COLOURS,
                              category_orders={"group": by_last_value(yearly, "start_year", "trials", "group")},
                              labels={"start_year": "Year started", "trials": "Trials", "group": ""},
                              title="Trials started each year, by new group")
                c1.plotly_chart(fig, width="stretch")

            flags = (latest[latest["metric"] == "v2_suicide_flag_by_condition"]
                     .rename(columns={"category": "group", "value": "trials"})
                     .assign(group=lambda d: relabel(d["group"])))
            if len(flags):
                flags = flags.sort_values("trials")
                fig = px.bar(flags, x="trials", y="group", orientation="h",
                             labels={"trials": "Trials", "group": ""},
                             title="Trials flagged for suicide or self-harm, by condition group")
                c2.plotly_chart(fig, width="stretch")

            m1, m2 = st.columns(2)
            m1.metric("Trials not in the published analysis", f"{one_new('v2_trials_extended'):,}",
                      help="Trials in the 2010–2025 window that are not among the 14,724 published trials, "
                           "most of them found by the second search.")
            m2.metric("Trials flagged for suicide or self-harm", f"{one_new('v2_trials_with_suicide_flag'):,}",
                      help="Any trial in the window, published or new groups, whose conditions or title "
                           "mention suicide, self-harm or self-injury.")
