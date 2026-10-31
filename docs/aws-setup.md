# Setting up the weekly refresh on AWS

These steps deploy `template.yaml` to a personal AWS account. They assume Windows, macOS or Linux with Python 3.12 or later. Region `us-east-2` (Ohio) is used throughout, because the account's project was created there and new-experience projects are locked to one Region.

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

1. AWS CLI version 2, then sign in with `aws login --region us-east-2 --profile personal`. If antivirus software inspects secure connections (Norton's Web/Mail Shield does), point the `AWS_CA_BUNDLE` environment variable at a certificate file that includes the antivirus root certificate, or the sign-in fails with `CERTIFICATE_VERIFY_FAILED`.
2. AWS SAM CLI.
3. Check both: `aws sts get-caller-identity --profile personal` and `sam --version`.

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

Run it with `--profile personal`, and answer the prompts with stack name `trials-refresh`, region `us-east-2`, your email for `AlertEmail`, and yes to saving the settings. Later deploys only need `sam build && sam deploy`.

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
region = "us-east-2"
bucket = "THE_BUCKET_NAME"
```

3. Save. The app restarts and the Latest refresh tab shows the counts.

Never commit these keys to the repository.

## 9. Add the PostgreSQL database

The stack also creates a PostgreSQL 17 database on RDS (db.t4g.micro, 20 GB gp3, one zone, one day of backups). After each refresh, the load function copies the newest snapshot into it, and Power BI can read it.

### What it costs

Approximate us-east-2 list prices, per month:

| Item | Always on | Weekly window (default) |
|---|---|---|
| db.t4g.micro instance | USD 11.68 (730 h) | about USD 0.18 (2.5 h each Monday) |
| 20 GB gp3 storage | USD 2.30 | USD 2.30 |
| Public IPv4 address, charged while running | USD 3.65 | about USD 0.06 |
| Secrets Manager secret (admin password) | USD 0.40 | USD 0.40 |
| VPC, S3 gateway endpoint, load function, SSM parameter | 0 | 0 |
| Total | about USD 18 | about USD 3, plus USD 0.02 per hour you run it by hand |

If the account's free tier includes RDS (750 hours of db.t4g.micro and 20 GB of storage a month), the instance and storage lines are free. On the Free plan, charges come out of the credits. Check Billing and Cost Management, Free Tier, a day after deploying.

There is no NAT gateway (about USD 33 a month). The load function has no internet access and does not need it.

`DatabaseHours` picks the schedule. `weekly-window` starts the database Mondays at 05:00 and stops it at 07:30 Toronto time, which covers the 06:00 refresh and the load that follows. `always-on` leaves it running. RDS starts a stopped database by itself after 7 days; the Monday schedule stops it again.

### Who can reach it

| From | How |
|---|---|
| Your home IP (`HomeIpCidr`) | port 5432, TLS required; used by Power BI and the setup script |
| The load function | port 5432 inside the VPC, IAM token instead of a password |
| Anyone else | blocked by the security group |

Database users: `trials_admin` (password in Secrets Manager, used only by the setup script), `loader` (IAM sign-in only; replaces the tables), `powerbi` (read-only; password in SSM Parameter Store at `/trials-refresh/powerbi-password`).

### Deploy it

1. Find your home IP address at https://checkip.amazonaws.com.
2. From the repository root, run `sam build`, then `sam deploy --guided --profile personal`. Keep the saved answers, enter your IP with `/32` for `HomeIpCidr` (for example `203.0.113.7/32`), and press Enter for `DatabaseHours` to keep `weekly-window`. The first deploy with the database takes about 15 minutes.
3. Create the database users and load the newest snapshot:

```
uv run --with boto3 --with pg8000 python tools/setup_database.py --profile personal
```

The script starts the database if it is stopped, creates `loader` and `powerbi`, saves the `powerbi` password, runs the load function and prints the row counts. If it fails to connect, your IP has probably changed (step 1).

From then on, each Monday refresh loads the database by itself. A failed load emails `AlertEmail`, like a failed refresh.

To check the database engine version is still offered before a first deploy: `aws rds describe-db-engine-versions --engine postgres --engine-version 17.9 --profile personal`. If the list is empty, change `EngineVersion` in `template.yaml` to a 17.x version that is listed.

### Connect Power BI

Power BI only connects to a server whose certificate it trusts, and RDS uses its own certificate authority.

1. Download https://truststore.pki.rds.amazonaws.com/us-east-2/us-east-2-bundle.p7b.
2. In PowerShell: `Import-Certificate -FilePath $HOME\Downloads\us-east-2-bundle.p7b -CertStoreLocation Cert:\CurrentUser\Root`, and answer Yes to each prompt.
3. With the weekly window, start the database first: `aws rds start-db-instance --db-instance-identifier DATABASE_ID --profile personal` (the `DatabaseId` output), and wait about 5 minutes.
4. Get the password: `aws ssm get-parameter --name /trials-refresh/powerbi-password --with-decryption --query Parameter.Value --output text --profile personal`.
5. In Power BI Desktop, choose Get data, PostgreSQL database. Server: the `DatabaseEndpoint` output. Database: `trials`. Data connectivity mode: Import. On the credentials screen, choose Database and enter `powerbi` and the password.
6. Pick the tables. Power BI finds the relationships from the foreign keys on `nct_id`.

Use a new report or a copy of the `.pbix`, so the published report keeps reading the 1 October 2026 CSV files. Stop the database when you are done (`aws rds stop-db-instance` with the same identifier), or the Monday schedule stops it.

### When your home IP changes

Run `sam deploy --guided --profile personal` again and enter the new address for `HomeIpCidr`. Only the security group rule changes.

## What runs and when

| Piece | Setting |
|---|---|
| Schedule | Mondays 06:00 America/Toronto (`template.yaml`, `ScheduleExpression`) |
| Function | Python 3.12, 1,536 MB memory, 15-minute timeout, no automatic retries |
| Checks | downloaded count equals the API's total; trials in the 2010–2025 window may not drop more than 10% from the last snapshot (`MAX_DROP`) |
| Storage | S3, public access blocked; raw pages move to Standard-IA after 30 days |
| Alerts | any function error emails `AlertEmail` |
| Logs | CloudWatch, kept 90 days |
| Database | PostgreSQL 17 on RDS db.t4g.micro, loaded after each refresh; Mondays 05:00 to 07:30 only with `DatabaseHours=weekly-window` |

To pause the refresh, disable the schedule in the EventBridge Scheduler console. To remove everything except the bucket, run `sam delete --stack-name trials-refresh`; the database is deleted without a final snapshot (every table can be rebuilt from S3), and the bucket is kept so snapshots are not lost, and can be emptied and deleted in the S3 console.
