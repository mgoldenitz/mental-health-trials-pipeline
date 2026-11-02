# v2 condition groups

Added in November 2026, after the research report and council review in the project files ("Expanding tracker condition scope"). The published analysis (download of 1 October 2026, 14,724 trials in eight groups) does not change.

## What was added

Four condition groups, matched by `rules.NEW_GROUPS`:

- ADHD: "attention deficit" followed by "hyperactivity" or "disorder", "ADHD", "hyperkinetic disorder". "Attention deficits" on its own is a cognitive symptom (in schizophrenia, for example) and is left out, and so is a bare "hyperactivity", which also matches bladder and airway trials.
- Autism spectrum: "autis", "Asperger", "pervasive developmental". "ASD" is left out because it also means atrial septal defect and acute stress disorder.
- Personality disorders: "personality disorder", "borderline personality", "antisocial personality", "schizotypal personality", "psychopathy". "BPD" is left out because it also means bronchopulmonary dysplasia.
- Gambling & gaming disorders: "gambl", "gaming disorder", "internet gaming", "gaming addiction", "video game addiction", "internet addiction", "problematic internet use".

A suicide or self-harm flag (`rules.SUICIDE`, the `suicide_flag` column on `trials`): true when any of a trial's condition names, or its title, mentions suicide, self-harm, self-injury or NSSI. It is a flag, not a group, because DSM-5-TR lists suicidal behaviour and self-harm as conditions that may be a focus of clinical attention, not as mental disorders. It also marks self-injurious behaviour in autism trials. It covers every kept trial, in the published groups and the new ones; trials whose only condition is suicide or self-harm are not downloaded.

## How the published counts stay fixed

- `fetch.EXTRA_COND` is a second API search, run after the first one (`fetch.QUERY_COND`, unchanged). A trial both searches return is kept once, as part of the first.
- Each condition keeps its published group (`rules.GROUPS`, first match), and also gets a row for every v2 group it matches. "Social anxiety in autistic adults" is in Anxiety, as before, and in Autism spectrum.
- `trials.scope` is `core` when the first search returned the trial and it has a published group, which is exactly the published analysis, and `extended` otherwise.
- `transform.counts` computes every published metric from core trials and published groups only, and adds metrics starting with `v2_` for the new groups and the flag.

Checked on the 1 October 2026 download: `tools/check_against_published.py` still matches all four published tables for the 14,724 core trials, and every published metric in `counts.csv` equals `data/baseline/counts_2026-10-01.csv`. That download came from the first search only, so it adds just the new-group trials the first search already returned: 49 extended trials and these trials in the window (core and extended):

| Group | Trials |
|---|---|
| Autism spectrum | 120 |
| Personality disorders | 80 |
| ADHD | 59 |
| Gambling & gaming disorders | 9 |
| Suicide or self-harm flag | 274 |

The full counts come from the first weekly run after deploying, which runs both searches.

## What changes downstream

- S3: the second search's raw pages go to `raw/<date>/extra/`. The four tables hold both scopes, and `trials` has two new columns, `scope` and `suicide_flag`.
- Streamlit: the Latest refresh tab keeps comparing the published metrics with the baseline and adds a table for the new groups and the flag.
- Athena: the latest database (`mental_health_trials`) now holds extended trials and v2 group rows, so the 11 queries in `athena/` return more rows there. Add `t.scope = 'core'` and leave out the v2 groups to match the published analysis. The published database is unchanged, and its trials have `scope` = `core` once `tools/upload_published_parquet.py` is run again (optional; without it `scope` is empty). `athena/v2/new_condition_groups.sql` summarises the new groups.
- PostgreSQL and the live Power BI report: `trials` gains `scope` and `suicide_flag`. Until the report filters on `scope` = `core`, its totals will include extended trials and its condition visuals will show the four new groups.

## Deploying

1. Optional check before deploying, from `src/` on your PC: `python -m pipeline --fetch --out ../out/v2-check`. It runs both searches and writes `counts.csv` with the `v2_` metrics.
2. `sam build` and `sam deploy` as in `docs/aws-setup.md`. The Glue tables pick up the two new columns.
3. Run the refresh once (`aws lambda invoke`) or wait for Monday 06:00. The RDS load follows on its own.
4. In Power BI Desktop, add a report-level filter `trials[scope]` = `core` to the existing pages, and add a page for the new groups if you want one.
