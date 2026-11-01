# Health Canada clinical trials

A second Lambda function, `HealthCanadaFunction`, runs every Monday at 06:30 Toronto time, 30 minutes after the ClinicalTrials.gov refresh. It downloads Health Canada's Clinical Trials Database API, keeps the mental health trials and saves them to the same S3 bucket under `health-canada/`.

## Source

Health Canada lists every clinical trial it has approved since 2013-04-01 for drugs and biologics (phases 1 to 3, in patients). On 2026-07-29 the public search moved to the [Clinical Trials Search Portal](https://clinical-trials-search.canada.ca/en), which replaced the 2013 Clinical Trials Database website. The database's [JSON API](https://health-products.canada.ca/api/documentation/cta-documentation-en.html) still works and is still updated: a download on 2026-10-31 had 9,757 protocols approved from 2013-04-02 to 2026-10-29. The portal links to it as "Accessing our data (API)". Licence: Open Government Licence - Canada.

The function calls three endpoints, each of which returns every record in one response when called without an id:

| Endpoint | What it holds | Size on 2026-10-31 |
| --- | --- | --- |
| `protocol` | one row per trial: control number, titles, dates, status code, conditions | 9,757 rows, 5.9 MB |
| `drugproduct` | one row per drug in a trial: brand name, manufacturer | 9,816 rows, 1.7 MB |
| `status` | names for the protocol's status codes: Ongoing, Closed, Pending | 3 rows |

The API has no trial phase, sites or ClinicalTrials.gov ID. The portal's CSV export has those (plus text statuses such as Recruiting and Closed), but Health Canada builds it as a background job that took 826 seconds on 2026-10-31, too close to Lambda's 900-second limit to run in one call. The portal's control number equals the API's `submission_no`, so the two can be joined later.

## Mental health filter

A trial is kept when any of its Health Canada condition names matches one of the eight groups in `src/pipeline/rules.py`, the same rules the ClinicalTrials.gov tables use. The trial's `condition_group` is the first matching group; `hc_conditions` keeps every condition with its own group. `psychedelic_class` uses the same drug rules, checked against the drug brand names and then the title.

On the 2026-10-31 download the shared rules matched 263 of 9,757 trials. Three condition names were false matches, so `HC_EXCLUDE` in `src/pipeline/health_canada.py` removes them: ACUTE POST-TRAUMATIC HEADACHES, POSTTRAUMATIC JOINT CONTRACTURES and OPIOID-INDUCED CONSTIPATION (6 trials). The exclusion lives in the Health Canada module so the ClinicalTrials.gov tables still reproduce the published numbers.

Names outside the eight groups stay out, matching the published scope. On 2026-10-31 these included AUTISM SPECTRUM DISORDER (18 trials), ADHD (15), INSOMNIA (18), ANOREXIA (9, of which 8 are anorexia nervosa; the shared rule needs the word "nervosa"), SUICIDALITY (6) and ALZHEIMER'S DISEASE (150).

Ketamine is flagged wherever it is listed as a drug, as in the ClinicalTrials.gov tables. In three Health Canada trials (191742, 206348, 183146) it is the anaesthetic for ECT, not the treatment under test.

## Output

| S3 key | Contents |
| --- | --- |
| `health-canada/raw/<date>/<endpoint>.json.gz` | API responses as downloaded |
| `health-canada/snapshots/<date>/hc_trials.csv` | one row per mental health trial |
| `health-canada/snapshots/<date>/hc_conditions.csv` | every condition of those trials, with its group |
| `health-canada/snapshots/<date>/hc_drugs.csv` | every drug in those trials, with its manufacturer |
| `health-canada/snapshots/<date>/counts.csv`, `manifest.json` | headline figures and run details |
| `health-canada/latest/`, `health-canada/history/counts.csv` | newest counts, manifest and `hc_trials.csv`, and every run's counts |
| `athena/health_canada/<table>/` | Parquet copies, queried in Athena as `mental_health_trials.hc_trials`, `hc_conditions`, `hc_drugs` |

A run fails, saves no snapshot and emails you through the existing alert topic if the protocol endpoint returns nothing or the number of protocols drops by more than 10% since the last run.

## Run it on your own computer

```
python tools/health_canada_local.py --out out/hc
```

This downloads the three endpoints (the protocol call can take a few minutes), writes the three tables and `counts.csv`, and lists every condition name the rules matched in `matched_conditions.csv` so you can check the filter.

## Try it after deploying

```
sam build
sam deploy --profile personal
aws lambda invoke --function-name <HealthCanadaFunctionName output> --profile personal out.json
```

Then in Athena (workgroup `trials-refresh`):

```sql
SELECT condition_group, COUNT(*) AS trials
FROM mental_health_trials.hc_trials
GROUP BY condition_group
ORDER BY trials DESC;
```

## In PostgreSQL and Power BI

The load function copies the Health Canada tables into the RDS database as `hc_trials`, `hc_conditions`, `hc_drugs` and `hc_snapshot_counts`, next to the ClinicalTrials.gov tables, and gives the `powerbi` user read access. It runs after each refresh writes its history file: at about 06:00 for ClinicalTrials.gov and 06:30 for Health Canada, both inside the database's Monday window. Each run loads the newest snapshot of both sources. In Power BI, tick the four `hc_` tables in the PostgreSQL navigator and join them to each other on `control_number`.

## In the Streamlit app

The Canada tab has a Health Canada approvals section below the ClinicalTrials.gov charts. It reads `health-canada/latest/counts.csv`, `manifest.json` and `hc_trials.csv` with the app's AppReader key, whose policy allows `health-canada/latest/*` and `health-canada/history/*`. It shows the number of mental health trials, all approved trials, ongoing trials and psychedelic or ketamine trials, charts by condition and by year approved, and a table of ongoing trials. The sidebar filters do not apply to it. The table appears after the first run that writes `latest/hc_trials.csv` (the Monday run after deploying, or a manual invoke).
