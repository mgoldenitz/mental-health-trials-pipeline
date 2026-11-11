"""Find trials page: search the weekly (or published) trials and open a registry record."""
from functools import partial

import streamlit as st

import tracker as t


@st.dialog("Trial details", width="large", position="right")
def trial_drawer(nct_id):
    t.show_trial_details(nct_id)


def open_selected(key, nct_ids):
    """Callback for a row click: remember which trial to show in the drawer."""
    rows = st.session_state[key].selection.rows
    if rows:
        st.session_state["open_trial"] = nct_ids[rows[0]]


# A fragment: typing in the search box or clicking a row reruns only this part of the page
@st.fragment
def results():
    f = t.current_filters()
    can_recruit = ((not f["outcome"] or "Ongoing or unknown" in f["outcome"])
                   and (not f["status"] or "Recruiting" in f["status"]))
    search_col, recruit_col = st.columns([5, 2], vertical_alignment="bottom")
    with search_col:
        query = st.text_input(
            "Search trial titles, sponsors or interventions",
            placeholder="Search titles, sponsors, or interventions…",
            key="q", bind="query-params", label_visibility="collapsed")
    with recruit_col:
        recruiting_first = st.checkbox(
            "Recruiting first", value=True, disabled=not can_recruit,
            help=None if can_recruit else
            "Recruiting trials are hidden by the Outcome or Recruitment status filter. Include "
            "\"Ongoing or unknown\" and \"Recruiting\" to use this.")

    weekly = t.weekly_search_data()
    if isinstance(weekly, tuple):
        search_trials, search_conditions, search_interventions, search_sites, manifest = weekly
        result_note = f"Updated {manifest['snapshot_date']} · Eight published groups"
    else:
        search_trials, search_conditions, search_interventions, search_sites = t.load_data()
        result_note = "Published snapshot · 1 October 2026 · Weekly data unavailable"
    search_view = t.apply_filters(search_trials, search_conditions, search_interventions, search_sites)
    table = search_view
    if query:
        q = query.strip()
        intervention_ids = search_interventions.loc[
            search_interventions["intervention_name"].str.contains(q, case=False, na=False, regex=False),
            "nct_id"]
        table = search_view[search_view["title"].str.contains(q, case=False, na=False, regex=False)
                            | search_view["sponsor_name"].str.contains(q, case=False, na=False, regex=False)
                            | search_view["nct_id"].isin(intervention_ids)]
    if recruiting_first and can_recruit:
        table = table.assign(_r=table["overall_status"].ne("RECRUITING")).sort_values(
            ["_r", "start_year"], ascending=[True, False]).drop(columns="_r")
    else:
        table = table.sort_values("start_year", ascending=False)

    if table.empty:
        st.info("No trials match this search and these filters. Try a shorter search term or clear a filter.")
        return

    result_table = table[["nct_id", "link", "title", "conditions", "treatments", "phase", "status",
                          "start_year", "enrollment", "sponsor_name", "countries"]].reset_index(drop=True)
    # Status as a one-item list so the table can draw it as a coloured pill
    result_table["status"] = result_table["status"].map(lambda s: [s] if isinstance(s, str) else [])
    status_options = sorted({s for row in result_table["status"] for s in row} | set(t.STATUS_COLOURS))
    status_colours = [t.STATUS_COLOURS.get(s, "gray") for s in status_options]
    nct_ids = result_table["nct_id"].tolist()
    # A new key whenever the rows change, so an old selection never points at the wrong trial
    result_key = f"trial_results_{hash(tuple(nct_ids))}"
    st.caption(f"**{len(table):,} trials** · {result_note} · Select a row to see its current registry record")
    st.dataframe(
        result_table,
        column_config={
            "nct_id": None,
            "link": st.column_config.LinkColumn("Trial", display_text=r"study/(NCT\d+)", pinned=True),
            "title": st.column_config.TextColumn("Title", width="large"),
            "conditions": "Condition",
            "treatments": "Treatment type",
            "phase": "Phase",
            "status": st.column_config.MultiselectColumn("Status", options=status_options,
                                                         color=status_colours, width="medium"),
            "start_year": st.column_config.NumberColumn("Start", format="%d"),
            "enrollment": st.column_config.NumberColumn("Enrolment", format="%d"),
            "sponsor_name": "Sponsor",
            "countries": "Countries",
        },
        hide_index=True, width="stretch", height=560, row_height=30,
        on_select=partial(open_selected, result_key, nct_ids), selection_mode="single-row", key=result_key,
        alt="Table of trials matching the search and filters, with links to ClinicalTrials.gov.",
    )
    nct_id = st.session_state.pop("open_trial", None)
    if nct_id:
        trial_drawer(nct_id)

    # The CSV is built only when the button is clicked, not on every rerun
    st.download_button("Download these trials (CSV)", lambda: table.to_csv(index=False),
                       file_name="trials_filtered.csv", mime="text/csv", icon=":material/download:")


results()
