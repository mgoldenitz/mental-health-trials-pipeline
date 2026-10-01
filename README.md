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

Interventional trials that started between 2010 and 2025, for eight DSM-5-aligned condition groups:

- Depression
- Anxiety
- OCD
- PTSD
- Bipolar disorder
- Schizophrenia & psychosis
- Substance use
- Eating disorders

OCD and PTSD are separate groups because DSM-5 moved them out of the anxiety disorders. Conditions the search wasn't designed to capture (e.g. ADHD, autism, dementia) are out of scope, even when they appear in a matched trial.

## Data
- **Source:** ClinicalTrials.gov API (version 2), U.S. National Library of Medicine
- **Downloaded:** 1 October 2026
- **Search:** `query.cond` = depression OR anxiety OR PTSD OR "bipolar disorder" OR schizophrenia OR psychosis OR "substance use disorder" OR "obsessive-compulsive disorder" OR "eating disorder" OR "anorexia nervosa" OR "bulimia nervosa" OR "binge eating disorder"; study type = interventional; start date 2010-01-01 to 2025-12-31.
- **Result:** 18,357 studies, downloaded 1 October 2026. The number of records downloaded matched the API's reported total.
The registry is updated daily, so re-running the download later will give slightly
different numbers. All results in this project refer to the 1 October 2026 download.

## Condition grouping

Each trial lists one or more conditions as free text. I assigned each listed condition to a group with keyword rules:

1. **Exclusions are checked first.** Conditions that share a keyword but aren't psychiatric (respiratory or CNS depression, surgical, dental or procedural anxiety, traumatic brain injury) are left ungrouped.
2. **The first matching group wins.** A condition such as "Depression and Anxiety" is counted under Depression.
3. **A trial can belong to several groups** if it lists several conditions, so trial counts by group add up to more than the total.

**Condition rows per group:**

| Group | Condition rows |
|---|---|
| Depression | 7,893 |
| Anxiety | 4,763 |
| Schizophrenia & psychosis | 3,021 |
| PTSD | 1,801 |
| Substance use | 1,307 |
| Eating disorders | 891 |
| Bipolar disorder | 783 |
| OCD | 449 |
| Other (ungrouped) | 19,728 |

**Fixes made after checking the most common ungrouped conditions:**

- PTSD: matched "Post Traumatic" written with a space or hyphen
- Psychosis: whole words only, so "Psychosocial" no longer matches
- OCD: removed "compulsive", which matched unrelated conditions
- Anxiety: excluded presurgical, dental and procedural anxiety
- Substance use: narrowed "alcohol" to use-disorder terms, so "Alcohol Aftereffects" no longer matches

**What stays in Other:**

- Generic labels ("Mental Disorder", "Mood Disorders")
- Co-occurring conditions (pain, insomnia, stress, obesity)
- Suicidal ideation, which may become a separate yes/no flag later
- Conditions outside the search's scope

A possible upgrade is grouping by MeSH terms from the API (`conditionBrowseModule`) instead of keywords.

## Status
In progress: data pull and SQL analysis (October 2026); AWS pipeline (November 2026).

Data: ClinicalTrials.gov, U.S. National Library of Medicine.
