# Mental Health Clinical Trials Pipeline

How is mental health treatment research changing? An analysis of interventional
clinical trials registered on ClinicalTrials.gov, 2010–2025.

## Key findings

Based on 14,713 interventional trials that started 2010–2025 and list at least one of eight DSM-5-aligned conditions.

- **Research on common disorders grew far faster than research on serious mental illness.** Comparing 2010–12 with 2023–25, anxiety trials grew 5.7×, eating disorders 3.6×, substance use 3.5× and depression 2.5×, while schizophrenia and bipolar disorder grew only 1.2×.
- **Non-drug treatments now dominate.** Drug trials stayed roughly level (277 in 2010, 251 in 2025), but behavioural trials grew 3.4× (203 → 691) and device trials 10× (27 → 272), driven by brain stimulation (TMS, tDCS) and virtual reality. Drugs fell from 44% to 15% of treatment types.
- **Universities and hospitals now sponsor nearly 9 in 10 trials.** Industry trials halved from 2010 to 2015 (134 → 69), then recovered to 126 by 2025, while academic trials grew 3.5× (366 → 1,269). Industry's share fell from 24% to 9%.
- **Industry and academia stop trials for different reasons.** Industry trials stop early more often (15.9% vs 12.3%), mostly because of business decisions (27% of stated reasons) or lack of efficacy (17%). Academic trials stop because of recruitment (29%), funding (19%) and COVID-19 (14%). Safety was the stated reason in fewer than 1% of cases.
- **Psychedelic trials surged after 2020.** 80% of the 165 psychedelic/MDMA trials started in 2021 or later, and they have outnumbered ketamine trials since 2023. Universities led the surge, but industry is overrepresented: it sponsors 23% of recent psychedelic trials, compared with about 9% of all trials.
- **Canada ranks second.** 1,020 trials (6.9%) include a Canadian site, second only to the United States (6,438; 43.8%) in this registry, and roughly 25 trials per million people compared with about 19 in the US. Toronto's CAMH is a top-5 sponsor in four condition groups.
- **COVID-19 left a clear mark.** In 2020, seven of eight condition groups started fewer trials; in 2021, all eight rose. Anxiety trials stepped up in 2021 and stayed higher, and COVID-specific trials explain only a small part of that rise.

**Caveats:** ClinicalTrials.gov is US-based, so many European and Asian trials register elsewhere. Overall registration grew over this period, so comparisons between groups are more reliable than raw growth. Condition groups come from my own keyword rules (see Condition grouping and Validation below).

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
- **Analysis set:** 14,713 of the 18,357 trials (80%) list at least one grouped condition and are used in the analysis. The other 3,644 list only ungrouped conditions (e.g. pain, insomnia, healthy volunteers, or generic labels such as "Mental Disorder").
  
The registry is updated daily, so re-running the download later will give slightly
different numbers. All results in this project refer to the 1 October 2026 download.

The raw download (`trials_raw.json`) and database (`trials.db`) aren't stored here because they're large; run the notebook to rebuild them.

Run the notebook to rebuild the raw data and database.

## Condition grouping
Each trial lists one or more conditions as free text. I assigned each listed condition to a group with keyword rules:
1. **Exclusions are checked first.** Conditions that share a keyword but aren't psychiatric (respiratory or CNS depression; pre-, peri- or postoperative, dental or procedural anxiety; kinesiophobia; traumatic brain injury) are left ungrouped.
2. **The first matching group wins.** A condition such as "Depression and Anxiety" is counted under Depression.
3. **A trial can belong to several groups** if it lists several conditions, so trial counts by group add up to more than the total.

**Condition rows per group:**

| Group | Condition rows |
|---|---|
| Depression | 7,893 |
| Anxiety | 4,661 |
| Schizophrenia & psychosis | 3,021 |
| PTSD | 1,801 |
| Substance use | 1,307 |
| Eating disorders | 924 |
| Bipolar disorder | 783 |
| OCD | 449 |
| Other (ungrouped) | 19,797 |

**Fixes made after checking the most common ungrouped conditions:**

- PTSD: matched "Post Traumatic" written with a space or hyphen
- Psychosis: whole words only, so "Psychosocial" no longer matches
- OCD: removed "compulsive", which matched unrelated conditions
- Anxiety: excluded pre-, peri- and postoperative anxiety (in either word order), dental and procedural anxiety, and kinesiophobia (fear of movement in pain rehabilitation)
- Substance use: narrowed "alcohol" to use-disorder terms, so "Alcohol Aftereffects" no longer matches
- Eating disorders: added "disordered eating", ARFID written out in full ("avoidant restrictive food intake disorder") and "feeding disorder of infancy", found during validation

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

## Validation

I compared my counts with searches on the ClinicalTrials.gov website (condition + Interventional + start year), run on 1 October 2026:

| Check | My pipeline | Website | Result |
|---|---|---|---|
| Schizophrenia & psychosis, 2020 | 121 | 121 | Exact match |
| PTSD, 2022 | 143 | 149 | 96%; the website expands "PTSD" to related terms such as subclinical PTSD |
| Eating disorders, 2024 | 70 | 154 | See below |

**Eating disorders:** I downloaded the website's 154 trials and compared trial IDs. 87 of them are obesity, weight, diet and metabolic studies that the website's synonym expansion links to "eating disorder". 67 of those weren't in my download, because my search used exact phrases, and 20 were in my data but correctly not grouped as eating disorders. The check also found three wordings my rules missed (disordered eating, ARFID written out in full, feeding disorder of infancy). After adding them, all 67 genuine eating disorder trials on the website are captured. My count of 70 includes 3 trials the website search doesn't return.

## Status
- [x] Download from the ClinicalTrials.gov API (1 Oct 2026)
- [x] Clean, group conditions, flag psychedelic and ketamine treatments
- [x] Load into SQLite
- [x] SQL analysis (11 queries in `sql/`, results in `results/`)
- [x] Validate against ClinicalTrials.gov website searches
- [ ] Power BI dashboard
- [ ] AWS version (S3, Glue, Athena)
      
Data: ClinicalTrials.gov, U.S. National Library of Medicine
