"""
One-time setup of the PostgreSQL database, run from your own computer after `sam deploy`.

  uv run --with boto3 --with pg8000 python tools/setup_database.py --profile personal

What it does:
  1. starts the database if the weekly window has stopped it, and waits for it
  2. signs in as the admin user (password read from Secrets Manager)
  3. creates two database users:
       loader   signs in with an IAM token; owns and replaces the tables
       powerbi  read-only, with a new random password
  4. saves the powerbi password as an encrypted SSM parameter (free tier)
  5. runs the load function once and prints the row counts

Run it again at any time: it changes nothing that exists except the powerbi
password, which it replaces. Your home IP must match the stack's HomeIpCidr.
"""

import argparse
import json
import secrets
import ssl
from pathlib import Path

import boto3
import pg8000.native
from botocore.config import Config

CA_FILE = Path(__file__).resolve().parents[1] / "src" / "pipeline" / "rds-ca-bundle.pem"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="personal")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--stack", default="trials-refresh")
    args = ap.parse_args()

    aws = boto3.Session(profile_name=args.profile, region_name=args.region)
    stack = aws.client("cloudformation").describe_stacks(StackName=args.stack)["Stacks"][0]
    out = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}

    rds = aws.client("rds")
    db = rds.describe_db_instances(DBInstanceIdentifier=out["DatabaseId"])["DBInstances"][0]
    if db["DBInstanceStatus"] == "stopped":
        print("Starting the database (about 5 minutes)...")
        rds.start_db_instance(DBInstanceIdentifier=out["DatabaseId"])
    print("Waiting for the database to be available...")
    rds.get_waiter("db_instance_available").wait(DBInstanceIdentifier=out["DatabaseId"])

    admin = json.loads(aws.client("secretsmanager")
                       .get_secret_value(SecretId=out["DatabaseSecretArn"])["SecretString"])
    ctx = ssl.create_default_context(cafile=str(CA_FILE))
    con = pg8000.native.Connection(user=admin["username"], password=admin["password"],
                                   host=out["DatabaseEndpoint"], database="trials",
                                   ssl_context=ctx, timeout=30)

    password = secrets.token_urlsafe(24)   # letters, digits, - and _ only
    for statement in [
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'loader') "
        "THEN CREATE ROLE loader LOGIN; END IF; END $$",
        "GRANT rds_iam TO loader",
        "GRANT CONNECT ON DATABASE trials TO loader",
        "GRANT USAGE, CREATE ON SCHEMA public TO loader",
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'powerbi') "
        "THEN CREATE ROLE powerbi LOGIN; END IF; END $$",
        f"ALTER ROLE powerbi PASSWORD '{password}'",
        "GRANT CONNECT ON DATABASE trials TO powerbi",
        "GRANT USAGE ON SCHEMA public TO powerbi",
    ]:
        con.run(statement)
    con.close()
    print("Database users loader and powerbi are ready.")

    name = f"/{args.stack}/powerbi-password"
    aws.client("ssm").put_parameter(Name=name, Value=password, Type="SecureString",
                                    Overwrite=True,
                                    Description="Read-only Power BI sign-in for the trials database")
    print(f"Saved the powerbi password in SSM Parameter Store as {name}")

    print("Loading the newest snapshot...")
    resp = aws.client("lambda", config=Config(read_timeout=180)).invoke(FunctionName=out["LoadFunctionName"])
    body = resp["Payload"].read().decode()
    if resp.get("FunctionError"):
        raise SystemExit(f"The load function failed: {body}")
    print(body)
    print(f"\nPower BI server: {out['DatabaseEndpoint']}\nDatabase: trials\nUser: powerbi")
    print(f"Password: aws ssm get-parameter --name {name} --with-decryption "
          f"--query Parameter.Value --output text --profile {args.profile}")


if __name__ == "__main__":
    main()
