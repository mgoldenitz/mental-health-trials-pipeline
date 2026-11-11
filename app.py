"""
Mental Health & Psychedelic Trial Tracker
Michael Goldenitz

A Streamlit app built on the cleaned outputs of the Mental Health Clinical Trials Pipeline
(data/powerbi). Run locally with:  streamlit run app.py

This file sets up the page menu. Shared code is in tracker.py and each page is in views/.
Only the open page runs, so a filter change rebuilds that page's charts and nothing else.
"""

import streamlit as st

import tracker as t

st.set_page_config(
    page_title="Mental Health & Psychedelic Trial Tracker",
    page_icon=t.LOGO,
    layout="wide",
    menu_items={
        "About": "Mental Health & Psychedelic Trial Tracker: mental health clinical trials registered on "
                 f"ClinicalTrials.gov, 2010 to 2025. Code and methods: {t.REPO}",
        "Report a bug": f"{t.REPO}/issues",
        "Get help": None,
    },
)

# Pages that use the sidebar filters
EXPLORE = [
    st.Page("views/overview.py", title="Overview", icon=":material/insights:", default=True),
    st.Page("views/find_trials.py", title="Find trials", icon=":material/search:", url_path="find-trials"),
    st.Page("views/psychedelics.py", title="Psychedelic & Ketamine", icon=":material/science:",
            url_path="psychedelic-ketamine"),
    st.Page("views/canada.py", title="Canada", icon=":material/location_on:", url_path="canada"),
]
ABOUT = st.Page("views/about.py", title="About the data", icon=":material/info:", url_path="about")
# Weekly data that the sidebar filters do not apply to
WEEKLY = [
    st.Page("views/latest_refresh.py", title="Latest refresh", icon=":material/update:",
            url_path="latest-refresh",
            help="The newest weekly download next to the published counts of 1 October 2026."),
    st.Page("views/new_groups.py", title="New condition groups", icon=":material/add_circle:",
            url_path="new-groups",
            help="ADHD, autism spectrum, personality disorders, and gambling and gaming disorders."),
    st.Page("views/health_canada.py", title="Health Canada", icon=":material/verified:",
            url_path="health-canada",
            help="Mental health trials authorized by Health Canada since April 2013."),
]

# The unnamed section shows as plain links in the top bar; Weekly updates is a drop-down menu
page = st.navigation({"": EXPLORE + [ABOUT], "Weekly updates": WEEKLY}, position="top")

t.header()
if page in EXPLORE:
    t.render_filters()
    t.filter_summary(t.filtered_view())
page.run()
