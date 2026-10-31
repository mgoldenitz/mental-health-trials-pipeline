# Classifying why trials stopped with Amazon Bedrock

`sql/05b_why_stopped_grouped.sql` sorts the free-text "why stopped" reasons into eight groups with keyword rules. A quarter of the in-scope stopped trials (307 of 1,213) land in "Other / unclear", because a reason such as "PI moved to another institution" or "drug supply issues" matches none of the keywords. `tools/classify_why_stopped.py` sends the same reasons to Amazon Nova Micro on Bedrock and writes the model's labels next to the keyword groups, so the two can be compared.

## What it sends and what it costs

Only trials that are TERMINATED, WITHDRAWN or SUSPENDED and have a reason are sent: 1,213 trials in the published tables, with 1,073 distinct reason texts. Identical texts go once. Reasons are sent 40 per request, about 27 requests in all.

The script prints its estimate before it calls anything: about 28,000 input tokens and 6,400 output tokens, which is about USD 0.002 at Nova Micro's on-demand price (USD 0.035 per million input tokens and USD 0.14 per million output tokens when this was written; pass `--price-in` and `--price-out` if the Bedrock pricing page shows different numbers). After a run it prints the token counts Bedrock reported.

Labels are cached in `data/llm/why_stopped_labels.csv`, keyed by NCT ID and reason text. A second run sends only trials that are new or whose reason changed, so labelling a weekly snapshot costs a fraction of a cent. The job runs from your computer and is not part of the weekly Lambda function.

## Categories

The model picks one of eleven categories. The first eight match the keyword groups so the results line up; three are new:

Recruitment, Funding, Sponsor / business decision, Efficacy / futility, Safety, COVID-19, Investigator / staff, Other / unclear, plus Regulatory / ethics, Logistics / drug supply and Study design change.

As in the SQL, COVID-19 wins when the pandemic is the stated cause, even if the reason also mentions recruitment. The full instructions sent to the model are `SYSTEM_PROMPT` in the script. Temperature is 0.

## Running it

From the repository root, signed in with `aws login --profile personal`:

```
uv run --with boto3 python tools/classify_why_stopped.py
uv run --with boto3 python tools/classify_why_stopped.py --run --limit 40
uv run --with boto3 python tools/classify_why_stopped.py --run
```

The first command only prints the estimate. The second labels 40 reasons as a trial run; open `data/llm/why_stopped_labels.csv` and check a few. The third labels the rest (the 40 already labelled are skipped).

The defaults are profile `personal`, region `us-east-2` and model `us.amazon.nova-micro-v1:0`. The `us.` prefix is the US cross-Region inference profile, which Nova Micro needs outside us-east-1. If the call fails with AccessDeniedException, open Model access (or Model catalog) in the Bedrock console in us-east-2 and check that Nova Micro is available to the account.

To label a newer weekly snapshot:

```
aws s3 cp s3://trials-refresh-databucket-awtfqu6gorcq/snapshots/DATE/trials.csv out/trials.csv --profile personal
uv run --with boto3 python tools/classify_why_stopped.py --run --trials out/trials.csv
```

## Outputs

`data/llm/why_stopped_labels.csv` has one row per trial: NCT ID, reason, model label, model ID and date labelled.

`results/ml/I_why_stopped_llm_groups.csv` has the model's groups in the layout of `results/05b_why_stopped_grouped.csv` (trials, percent, industry, academic), with the keyword count beside each.

`results/ml/I_why_stopped_llm_vs_keyword.csv` crosses keyword group with model label and counts trials in each pair.

`results/ml/I_why_stopped_disagreements.csv` lists every trial where the two differ, for reading by hand.

The script also prints the share of trials where the two agree and how many fall in "Other / unclear" under each method.

The keyword rules in the script are a copy of the CASE expression in `sql/05b_why_stopped_grouped.sql` and reproduce its published counts exactly (332 Recruitment, 307 Other / unclear, 197 Funding, 146 COVID-19, 112 Investigator / staff, 62 Sponsor / business decision, 46 Efficacy / futility, 11 Safety). If the SQL changes, change `keyword_group()` to match.
