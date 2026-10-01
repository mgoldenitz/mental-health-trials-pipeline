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
- **Analysis set:** 14,792 of the 18,357 trials (81%) list at least one grouped condition and are used in the analysis. The other 3,565 list only ungrouped conditions (e.g. pain, insomnia, healthy volunteers, or generic labels such as "Mental Disorder").
  
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

## Treatment flag

Each intervention is checked for psychedelic and ketamine treatments:
- **Psychedelic / MDMA:** substance names (psilocybin, MDMA, LSD, DMT, 5-MeO-DMT, ayahuasca, ibogaine, mescaline and others) plus company drug codes, since industry trials often list only the code (e.g. COMP360, MM-120, CYB003, GH001, BPL-003, RE104, BMND08).
- **Ketamine / esketamine:** flagged separately because both are already approved treatments, unlike psilocybin or MDMA.
- Placebo arms named after a drug (e.g. "matched placebo") are excluded.
**Trials flagged (in scope):** 318 ketamine/esketamine, 165 psychedelic/MDMA. Out-of-scope trials removed: 25 ketamine (mostly anaesthesia, sedation and pain) and 7 psychedelic (healthy-volunteer studies, and two cancer trials that list only the cancer as the condition, even though anxiety is the focus).
I checked the 40 most common flagged names by hand; all were genuine treatments.

## Data model
The API's nested JSON is flattened into four tables, saved as CSV and loaded into SQLite (`trials.db`):
| Table | One row per | Rows | Key columns |
|---|---|---|---|
| `trials` | trial | 18,357 | nct_id, title, start_date, start_year, overall_status, why_stopped, phase, enrollment, sponsor_name, sponsor_class, in_scope |
| `conditions` | trial × condition | 40,636 | nct_id, condition, condition_group |
| `interventions` | trial × treatment | 32,628 | nct_id, intervention_type, intervention_name, psychedelic_class |
| `sites` | trial × country | 20,028 | nct_id, country |

All queries count `DISTINCT nct_id`, because joins repeat trials that have several conditions, treatments or countries.

## Status
- [x] Download from the ClinicalTrials.gov API (1 Oct 2026)
- [x] Clean, group conditions, flag psychedelic and ketamine treatments
- [x] Load into SQLite
- [ ] SQL analysis (in progress)
- [ ] Power BI dashboard
- [ ] AWS version (S3, Glue, Athena)
      
Data: ClinicalTrials.gov, U.S. National Library of Medicine
