# Mental Health Clinical Trials Pipeline

How is mental health treatment research changing? An analysis of interventional
clinical trials registered on ClinicalTrials.gov, 2010–2025.

## Questions
1. How has the number of mental health trials changed since 2010, by condition?
2. Which treatment types are growing: drug, behavioural, device, or psychedelic-assisted?
3. Who sponsors the research (industry, universities, government), and has that shifted?
4. How often do trials finish versus stop early, and does that differ by sponsor type?
5. Where does Canada fit: how many trials include a Canadian site, and in which conditions?

## Scope
Interventional studies starting 2010–2025, in six condition groups: depression, anxiety,
PTSD, bipolar disorder, schizophrenia and psychosis, and substance use disorders.

## Data
- **Source:** ClinicalTrials.gov API (version 2), U.S. National Library of Medicine
- **Downloaded:** 1 October 2026
- **Search:** conditions matching depression, anxiety, PTSD, bipolar disorder,
  schizophrenia, psychosis or substance use disorder; interventional studies only;
  start date 1 January 2010 to 31 December 2025
- **Result:** 17,581 studies (all downloaded; count matches the search total)

The registry is updated daily, so re-running the download later will give slightly
different numbers. All results in this project refer to the 1 October 2026 download.

## Status
In progress: data pull and SQL analysis (October 2026); AWS pipeline (November 2026).

Data: ClinicalTrials.gov, U.S. National Library of Medicine.
