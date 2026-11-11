"""
Shared code for the Mental Health & Psychedelic Trial Tracker app: data loading, the sidebar
filters, the page header and the chart style. app.py is the entrypoint; each page is in views/.
"""

from pathlib import Path
import io
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "powerbi"
BASELINE = ROOT / "data" / "baseline" / "counts_2026-10-01.csv"
RESULTS = ROOT / "results" / "10_results_reporting.csv"
LOGO = ROOT / "images" / "branding" / "evidence-constellation-mark.png"
CTGOV = "https://clinicaltrials.gov/study/"
REPO = "https://github.com/mgoldenitz/mental-health-trials-pipeline"

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


# ---------------------------------------------------------------- colours
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
US_SITE_COLOURS = {"With a US site": "#0072B2", "Without a US site": "#9DB9D3"}

# Brighter versions of the same hues for the dark theme, so every line stays readable on charcoal
GROUP_COLOURS_DARK = {
    "Anxiety": "#56B4E9",
    "Bipolar disorder": "#E07AB0",
    "Depression": "#EE8A3C",
    "Eating disorders": "#C49A7E",
    "OCD": "#B0A89A",
    "PTSD": "#2BB58A",
    "Schizophrenia & Psychosis": "#A98BD4",
    "Substance use": "#D8B54A",
}
NEW_GROUP_COLOURS_DARK = {
    "ADHD": "#56B4E9",
    "Autism spectrum": "#EE8A3C",
    "Gambling & gaming disorders": "#2BB58A",
    "Personality disorders": "#A98BD4",
}
US_SITE_COLOURS_DARK = {"With a US site": "#56B4E9", "Without a US site": "#4A6378"}

# Status pills in the Find trials table, using theme colour names so they suit light and dark mode
STATUS_COLOURS = {
    "Recruiting": "green",
    "Not yet recruiting": "blue",
    "Enrolling by invitation": "blue",
    "Active not recruiting": "violet",
    "Completed": "gray",
    "Suspended": "orange",
    "Terminated": "red",
    "Withdrawn": "red",
    "Unknown": "gray",
}


def is_dark():
    """True when the viewer sees the dark theme."""
    return st.context.theme.type == "dark"


def group_colours():
    return GROUP_COLOURS_DARK if is_dark() else GROUP_COLOURS


def new_group_colours():
    return NEW_GROUP_COLOURS_DARK if is_dark() else NEW_GROUP_COLOURS


def us_site_colours():
    return US_SITE_COLOURS_DARK if is_dark() else US_SITE_COLOURS


# ---------------------------------------------------------------- chart helpers
def other_last(df, col):
    """Rows sorted smallest to largest, with "Other" first so it is drawn at the bottom of a
    horizontal bar chart instead of among the real categories."""
    df = df.sort_values("trials")
    return pd.concat([df[df[col] == "Other"], df[df[col] != "Other"]])


def by_last_value(df, x, y, group):
    """Group names ordered by their value in the latest year, highest first, so the
    legend lists the lines in the same order they end on the chart."""
    return df.sort_values(x).groupby(group)[y].last().sort_values(ascending=False).index.tolist()


def chart(where, fig, alt=None):
    """Draw a Plotly figure in the editorial style: left-aligned serif title, hairlines on the
    value axis only, thousands separators on counts, and a description for screen readers.
    Colours and body font come from the theme in .streamlit/config.toml."""
    hairline = "rgba(120, 110, 95, 0.18)"
    fig.update_layout(
        title=dict(x=0, xanchor="left", font=dict(family="Newsreader, Georgia, serif", size=17)),
        legend=dict(title_text=fig.layout.legend.title.text or ""),
        margin=dict(t=56),
        bargap=0.45,
    )
    # Hairlines run along the value axis only: vertical for horizontal bars, horizontal otherwise
    horizontal = any(getattr(t, "orientation", None) == "h" for t in fig.data)
    value_axis, category_axis = (fig.update_xaxes, fig.update_yaxes) if horizontal else \
        (fig.update_yaxes, fig.update_xaxes)
    value_axis(showgrid=True, gridcolor=hairline, zeroline=False)
    category_axis(showgrid=False, linecolor=hairline, ticks="")
    # One number style on every count axis (6,000 rather than 6000 on one chart and 6k on another)
    axis = fig.layout.xaxis if horizontal else fig.layout.yaxis
    if axis.tickformat is None:
        value_axis(tickformat=",d")
    # Labels inside bars: white on the dark light-mode accent, charcoal on the pale dark-mode accent
    fig.update_traces(insidetextfont_color="#1C1A17" if is_dark() else "#FFFFFF", selector=dict(type="bar"))
    if alt is None:
        kind = "Line chart" if any(t.type == "scatter" for t in fig.data) else "Bar chart"
        alt = f"{kind}: {fig.layout.title.text}."
    where.plotly_chart(fig, width="stretch", alt=alt)


def share(part, whole, text):
    return f"{part / whole:.1%} {text}" if whole else None


def log_error(where, exc):
    """Write an error to the Community Cloud log without showing its details to visitors."""
    print(f"[tracker] {where}: {exc!r}", file=sys.stderr)
    sys.stderr.flush()


# ---------------------------------------------------------------- data
def enrich(trials, conditions, interventions, sites):
    """One row per trial with its condition groups, treatment types, psychedelic class and
    countries joined as text, plus readable phase, status and outcome labels."""
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
    return trials.reset_index()


@st.cache_data(show_spinner="Loading the published trials…")
def load_data():
    """The published analysis of 1 October 2026 (data/powerbi)."""
    trials = pd.read_csv(DATA / "trials.csv")
    conditions = pd.read_csv(DATA / "conditions.csv")
    interventions = pd.read_csv(DATA / "interventions.csv")
    sites = pd.read_csv(DATA / "sites.csv")
    conditions["condition_group"] = relabel(conditions["condition_group"])
    return enrich(trials, conditions, interventions, sites), conditions, interventions, sites


@st.cache_data(show_spinner=False)
def load_results():
    """Results-posting rates for completed trials (results/10_results_reporting.csv)."""
    return pd.read_csv(RESULTS)


@st.cache_data(show_spinner=False)
def load_baseline():
    """Published counts of 1 October 2026, compared with each weekly refresh."""
    return pd.read_csv(BASELINE)


def aws_secrets():
    """The [aws] block of the app's secrets, or None if it has none."""
    try:
        return dict(st.secrets["aws"])
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def _s3_client(region):
    """One S3 client shared by every visitor. Only called when secrets exist, so a missing-secrets
    result is never cached."""
    import boto3
    cfg = aws_secrets()
    return boto3.client("s3", aws_access_key_id=cfg["access_key_id"],
                        aws_secret_access_key=cfg["secret_access_key"], region_name=region)


def s3():
    """(client, bucket) for the weekly data, or None when the app has no AWS secrets."""
    cfg = aws_secrets()
    if not cfg:
        return None
    return _s3_client(cfg["region"]), cfg["bucket"]


def _read(client, bucket, key):
    return client.get_object(Bucket=bucket, Key=key)["Body"].read()


# The weekly refresh runs on Mondays. Six-hour caches are refreshed in the background, so the
# visitor who arrives after one expires still gets the cached copy straight away.
@st.cache_data(ttl="6h", refresh_mode="background", show_spinner="Loading this week's trials…")
def load_weekly_search_data(_client, bucket):
    """Load the latest S3 Parquet tables, limited to the eight published groups."""
    tables = {
        name: pd.read_parquet(io.BytesIO(_read(_client, bucket, f"athena/latest/{name}/{name}.parquet")))
        for name in ("trials", "conditions", "interventions", "sites")
    }
    manifest = json.loads(_read(_client, bucket, "latest/manifest.json"))
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
    interventions = tables["interventions"].loc[tables["interventions"]["nct_id"].isin(core_ids)].copy()
    sites = tables["sites"].loc[tables["sites"]["nct_id"].isin(core_ids)].copy()
    return enrich(trials, conditions, interventions, sites), conditions, interventions, sites, manifest


@st.cache_data(ttl="6h", refresh_mode="background", show_spinner="Loading the latest refresh…")
def load_refresh(_client, bucket):
    """Counts from the newest weekly download in S3."""
    latest = pd.read_csv(io.BytesIO(_read(_client, bucket, "latest/counts.csv")))
    manifest = json.loads(_read(_client, bucket, "latest/manifest.json"))
    history = pd.read_csv(io.BytesIO(_read(_client, bucket, "history/counts.csv")))
    return latest, manifest, history


@st.cache_data(ttl="6h", refresh_mode="background", show_spinner="Loading Health Canada trials…")
def load_health_canada(_client, bucket):
    """Counts and the trial list from the newest weekly Health Canada download in S3."""
    def read(key):
        return _read(_client, bucket, "health-canada/" + key)

    counts = pd.read_csv(io.BytesIO(read("latest/counts.csv")))
    manifest = json.loads(read("latest/manifest.json"))
    try:    # written from the 2026-11-02 run onward
        trials = pd.read_csv(io.BytesIO(read("latest/hc_trials.csv")), dtype={"control_number": str})
    except Exception:
        trials = None
    return counts, manifest, trials


def weekly_search_data():
    """The weekly Find trials tables, "error" if S3 could not be read, or None without secrets."""
    conn = s3()
    if conn is None:
        return None
    try:
        return load_weekly_search_data(*conn)
    except Exception as exc:
        log_error("weekly Find trials data", exc)
        return "error"


def weekly_refresh():
    """The latest refresh counts, "error" if S3 could not be read, or None without secrets."""
    conn = s3()
    if conn is None:
        return None
    try:
        return load_refresh(*conn)
    except Exception as exc:
        log_error("latest refresh", exc)
        return "error"


# ---------------------------------------------------------------- registry details
@st.cache_data(ttl="6h", max_entries=256, show_spinner="Loading the registry record…")
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
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        log_error(f"registry record {nct_id}", exc)
        st.warning("Trial details could not be loaded right now. "
                   "Open the ClinicalTrials.gov record to view the latest information.")
        st.link_button("Open on ClinicalTrials.gov", f"{CTGOV}{nct_id}")
        return

    protocol = record.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    description = protocol.get("descriptionModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    interventions_module = protocol.get("armsInterventionsModule", {})
    outcomes_module = protocol.get("outcomesModule", {})

    st.subheader(ident.get("briefTitle") or nct_id)
    verified = status.get("statusVerifiedDate")
    status_text = status.get("overallStatus", "Status not reported").replace("_", " ").title()
    st.caption(f"{nct_id} · {status_text}" + (f" · Last verified {verified}" if verified else ""))
    st.link_button("View full record and contact details on ClinicalTrials.gov", f"{CTGOV}{nct_id}")

    st.markdown("**Summary**")
    st.markdown(detail_text(description.get("briefSummary")))
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
    reported_outcomes = False
    for label, items in [("Primary", outcomes_module.get("primaryOutcomes", [])),
                         ("Secondary", outcomes_module.get("secondaryOutcomes", [])),
                         ("Other", outcomes_module.get("otherOutcomes", []))]:
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


# ---------------------------------------------------------------- filters
# Widget keys double as URL parameter names, so a filtered view can be shared as a link
FILTER_KEYS = ("condition", "treatment", "outcome", "phase", "years", "status", "country",
               "psychedelic", "canada")


def filter_options(weekly):
    """Choices for each sidebar filter, from the published data plus the weekly data when connected."""
    trials, conditions, interventions, sites = load_data()
    statuses = set(trials["status"].dropna())
    countries = set(sites["country"].dropna())
    if isinstance(weekly, tuple):
        statuses |= set(weekly[0]["status"].dropna())
        countries |= set(weekly[3]["country"].dropna())
    return {
        "groups": sorted(conditions["condition_group"].dropna().unique()),
        "treatments": sorted(interventions["treatment_type"].dropna().unique()),
        "outcomes": [o for o in OUTCOME_ORDER if o in set(trials["outcome"])],
        "phases": [p for p in PHASE_ORDER if p in set(trials["phase"])],
        "years": (int(trials["start_year"].min()), int(trials["start_year"].max())),
        "statuses": sorted(statuses),
        "countries": sorted(countries),
    }


def clear_filters():
    """Callback for the Clear all filters button: put every filter and the search box back to its
    default. Values are set rather than deleted, because a deleted value would come back from the
    session store that keeps filters across pages."""
    trials = load_data()[0]
    for key in ("condition", "treatment", "outcome", "phase", "status", "country"):
        st.session_state[key] = []
    st.session_state["years"] = (int(trials["start_year"].min()), int(trials["start_year"].max()))
    st.session_state["psychedelic"] = False
    st.session_state["canada"] = False
    st.session_state["q"] = ""


def render_filters():
    """Draw the sidebar filters. Values stay in the URL and in the session, so they carry
    across pages and survive a visit to a page without filters."""
    weekly = weekly_search_data()
    opts = filter_options(weekly)
    keep = dict(bind="query-params", persist_state="session")
    sb = st.sidebar
    sb.header("Filters")
    sb.multiselect("Condition", opts["groups"], placeholder="All conditions", key="condition", **keep)
    sb.multiselect("Treatment type", opts["treatments"], placeholder="All treatment types",
                   key="treatment", **keep)
    sb.multiselect(
        "Outcome", opts["outcomes"], placeholder="All outcomes",
        help="Ongoing or unknown covers trials still recruiting or running, "
             "plus trials whose status hasn't been updated in two years. "
             "Completed trials finished as planned. Stopped early covers "
             "trials that were terminated, suspended or withdrawn.",
        key="outcome", **keep)
    sb.multiselect(
        "Phase", opts["phases"], placeholder="All phases",
        help="Phase 1 tests safety in a small group, Phase 2 tests whether it works, "
             "Phase 3 confirms it in a large group, and Phase 4 follows it after approval. "
             "Combined phases (e.g. Phase 1/2) run two stages in one trial. "
             "Not applicable covers trials without drug phases, such as therapy or device studies.",
        key="phase", **keep)
    # The default range is passed only on first draw; after that the value lives in the session
    years_default = {} if "years" in st.session_state else {"value": opts["years"]}
    sb.slider("Year started", *opts["years"], key="years", **years_default, **keep)
    sb.multiselect("Recruitment status", opts["statuses"], placeholder="All statuses", key="status", **keep)
    sb.multiselect("Country", opts["countries"], placeholder="All countries", key="country", **keep)
    sb.toggle("Psychedelic & Ketamine trials only", key="psychedelic", **keep)
    sb.toggle("Trials in Canada", key="canada", **keep)
    sb.button("Clear all filters", icon=":material/filter_alt_off:", on_click=clear_filters,
              disabled=not active_filters(), width="stretch")

    if isinstance(weekly, tuple):
        sb.caption(
            f"Overview, psychedelic and Canada summary figures use the 1 October 2026 download. "
            f"Find trials uses the {weekly[4]['snapshot_date']} weekly refresh, limited to the eight "
            "published groups.")
    elif weekly == "error":
        sb.warning("Weekly trial data is unavailable; Find trials is showing the 1 October 2026 snapshot.")
    else:
        sb.caption("Data: ClinicalTrials.gov, downloaded 1 October 2026. The weekly Find trials feed is "
                   "not connected, so it is showing the published snapshot.")


def current_filters():
    """The filter values chosen in the sidebar, with defaults for any not set yet."""
    years = load_data()[0]["start_year"]
    f = {key: st.session_state.get(key) for key in FILTER_KEYS}
    for key in ("condition", "treatment", "outcome", "phase", "status", "country"):
        f[key] = f[key] or []
    f["years"] = tuple(f["years"] or (int(years.min()), int(years.max())))
    f["psychedelic"] = bool(f["psychedelic"])
    f["canada"] = bool(f["canada"])
    return f


def active_filters():
    """Short labels for each filter that narrows the trials, for the chips above the numbers."""
    f = current_filters()
    years = load_data()[0]["start_year"]
    labels = list(f["condition"]) + list(f["treatment"]) + list(f["outcome"]) + list(f["phase"])
    if f["years"] != (int(years.min()), int(years.max())):
        labels.append(f"Started {f['years'][0]} to {f['years'][1]}")
    labels += list(f["status"]) + list(f["country"])
    if f["psychedelic"]:
        labels.append("Psychedelic & Ketamine only")
    if f["canada"]:
        labels.append("In Canada")
    return labels


def apply_filters(df, conditions, interventions, sites):
    """Trials in df that match the sidebar filters."""
    f = current_filters()
    mask = df["start_year"].between(*f["years"])
    if f["condition"]:
        mask &= df["nct_id"].isin(conditions.loc[conditions["condition_group"].isin(f["condition"]), "nct_id"])
    if f["treatment"]:
        mask &= df["nct_id"].isin(
            interventions.loc[interventions["treatment_type"].isin(f["treatment"]), "nct_id"])
    if f["outcome"]:
        mask &= df["outcome"].isin(f["outcome"])
    if f["phase"]:
        mask &= df["phase"].isin(f["phase"])
    if f["status"]:
        mask &= df["status"].isin(f["status"])
    if f["country"]:
        mask &= df["nct_id"].isin(sites.loc[sites["country"].isin(f["country"]), "nct_id"])
    if f["psychedelic"]:
        mask &= df["psychedelic_class"].notna()
    if f["canada"]:
        mask &= df["in_canada"]
    return df[mask]


def filtered_view():
    """Published trials that match the sidebar filters."""
    trials, conditions, interventions, sites = load_data()
    return apply_filters(trials, conditions, interventions, sites)


# ---------------------------------------------------------------- header
def header():
    """Logo, kicker and title, shown on every page."""
    st.logo(LOGO, size="large")
    st.caption("CLINICAL TRIALS REGISTRY ANALYSIS · 2010–2025")
    st.title("Mental Health & Psychedelic Trial Tracker")


def filter_summary(view):
    """Active filter chips, a Clear button when nothing matches, and the four headline numbers."""
    trials = load_data()[0]
    labels = active_filters()
    if labels:
        with st.container(horizontal=True, gap="xsmall"):
            st.caption("Filtered by", width="content")
            for label in labels:
                st.badge(label, color="primary")
    else:
        st.caption("Search and explore mental health clinical trials registered on ClinicalTrials.gov. "
                   "Use the filters in the sidebar; every chart and table on these pages updates with them.")

    if view.empty:
        st.warning("No published trials match these filters. Remove one, or clear them all.")
        st.button("Clear all filters", icon=":material/filter_alt_off:", on_click=clear_filters,
                  key="clear_main")
        return

    n_view = len(view)
    # A grid wraps the four numbers two by two on a phone instead of stacking them one per row
    with st.grid(4, min_column_width=165, gap="small"):
        st.metric("Trials", f"{n_view:,}",
                  share(n_view, len(trials), f"of all {len(trials):,}") if n_view < len(trials) else None,
                  delta_color="off", delta_arrow="off")
        for label, count in [
                ("Recruiting now", int((view["overall_status"] == "RECRUITING").sum())),
                ("Psychedelic & Ketamine", int(view["psychedelic_class"].notna().sum())),
                ("In Canada", int(view["in_canada"].sum()))]:
            st.metric(label, f"{count:,}", share(count, n_view, "of trials"),
                      delta_color="off", delta_arrow="off")
