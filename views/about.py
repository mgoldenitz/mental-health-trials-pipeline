"""About the data page."""
import streamlit as st

import tracker as t

st.subheader("About the data")
st.markdown(
    "The **Overview**, **Psychedelic & Ketamine** and **Canada** pages use the published 1 October 2026 "
    "download. **Find trials** uses the latest weekly refresh so its recruitment statuses stay current, "
    "while keeping only trials in the eight published condition groups. The pages under **Weekly updates** "
    "show separate weekly data and do not change published totals.")

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
    "groups are on the **New condition groups** page under Weekly updates.")

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

st.markdown("**Code and methods**")
st.markdown(f"The pipeline, notebooks and this app are on [GitHub]({t.REPO}).")
