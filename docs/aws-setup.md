# Setting up the weekly refresh on AWS

These steps deploy `template.yaml` to a personal AWS account. They assume Windows, macOS or Linux with Python 3.12 or later. Region `ca-central-1` (Canada Central) is used throughout; any region works if you use it consistently.

## 1. Freeze the published version

On GitHub, open Releases, choose "Draft a new release", create the tag `v1.0-published-2026-10-01` on `main`, and publish it. The tag marks the exact files behind the published findings, Power BI report and PDF.

## 2. Rename the repository (optional)

Streamlit Community Cloud loses track of an app whose repository is renamed, and the app becomes view-only. Do it in this order:

1. At share.streamlit.io, open the app's menu and delete the app.
2. On GitHub, rename the repository under Settings.
3. Deploy the app again from the renamed repository, with `app.py` as the entry file, and ask for the same subdomain (`mh-trials-tracker`). Streamlit's documentation does not say whether a freed subdomain can be reused straight away.
4. Update the app link at the top of the README if the subdomain changed, and the URL in `.github/scripts/wake_app.py`.

## 3. Secure the account and set a budget

1. Sign in as the root user, turn on MFA, and stop using root for daily work.
2. In IAM Identity Center (or IAM), create a user for yourself with administrator access and MFA.
3. In Billing and Cost Management, open Budgets and create a monthly cost budget (for example USD 5) with an email alert at 80% of actual spend.

## 4. Install the tools

1. AWS CLI version 2, then run `aws configure` (or `aws configure sso` for Identity Center) with region `ca-central-1`.
2. AWS SAM CLI.
3. Check both: `aws sts get-caller-identity` and `sam --version`.

## 5. Time a full download on your computer

The Lambda function stops after 15 minutes. From the `src/` folder:

```
python -m pipeline --fetch --out ../out/test
```

The script prints the elapsed time after each page of 1,000 studies (about 19 pages). If the whole download takes under about 10 minutes, Lambda is fine. If it takes longer, the job should move to ECS Fargate before you deploy.

The same command with `--raw path/to/trials_raw.json` instead of `--fetch` rebuilds the tables from a saved download, and `python tools/check_against_published.py out/test` (from the repository root) compares them with `data/powerbi/`.

## 6. Deploy

From the repository root:

```
sam build
sam deploy --guided
```

Answer the prompts with stack name `trials-refresh`, region `ca-central-1`, your email for `AlertEmail`, and yes to saving the settings. Later deploys only need `sam build && sam deploy`.

AWS then sends an email asking you to confirm the SNS subscription. Confirm it, or failure alerts will not arrive.

`sam deploy` prints the stack outputs: `BucketName`, `FunctionName` and `AppReaderUser`. Keep them for the next steps.

## 7. Run it once now

```
aws lambda invoke --function-name FUNCTION_NAME --invocation-type Event response.json
sam logs --stack-name trials-refresh --name RefreshFunction --tail
```

Replace FUNCTION_NAME with the `FunctionName` output. The log shows one line per page and ends with the run's manifest. In the S3 console, the bucket should now hold `raw/`, `snapshots/`, `latest/` and `history/` folders.

## 8. Connect the Streamlit app

1. In the IAM console, open the user named in `AppReaderUser`, choose Security credentials, and create an access key (use case: application running outside AWS). This user can only read `latest/` and `history/` in the bucket.
2. In Streamlit Community Cloud, open the app's Settings, then Secrets, and paste:

```
[aws]
access_key_id = "THE_ACCESS_KEY_ID"
secret_access_key = "THE_SECRET_ACCESS_KEY"
region = "ca-central-1"
bucket = "THE_BUCKET_NAME"
```

3. Save. The app restarts and the Latest refresh tab shows the counts.

Never commit these keys to the repository.

## What runs and when

| Piece | Setting |
|---|---|
| Schedule | Mondays 06:00 America/Toronto (`template.yaml`, `ScheduleExpression`) |
| Function | Python 3.12, 1,536 MB memory, 15-minute timeout, no automatic retries |
| Checks | downloaded count equals the API's total; trials in the 2010–2025 window may not drop more than 10% from the last snapshot (`MAX_DROP`) |
| Storage | S3, public access blocked; raw pages move to Standard-IA after 30 days |
| Alerts | any function error emails `AlertEmail` |
| Logs | CloudWatch, kept 90 days |

To pause the refresh, disable the schedule in the EventBridge Scheduler console. To remove everything except the bucket, run `sam delete --stack-name trials-refresh`; the bucket is kept so snapshots are not lost, and can be emptied and deleted in the S3 console.
