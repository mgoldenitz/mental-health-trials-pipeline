"""
AWS Lambda entry point: copy the newest snapshot from S3 into PostgreSQL on RDS.

Runs when the weekly refresh writes history/counts.csv (its last file), or by hand:
  aws lambda invoke --function-name LOAD_FUNCTION_NAME response.json

Tables (schema public, replaced in one transaction so readers never see a half load):
  trials, conditions, interventions, sites   the four Power BI tables of the snapshot
  snapshot_counts                            every snapshot's headline counts
  load_log                                   one row per load (kept across loads)

The function runs inside the database's VPC with no internet access. It reaches S3
through a gateway endpoint and signs in as the database user "loader" with an IAM
token, which is generated locally, so it needs no password and no Secrets Manager call.
"""

import io
import json
import os
import ssl
import time
from pathlib import Path

import boto3
import pg8000.native

s3 = boto3.client("s3")
BUCKET = os.environ.get("BUCKET")
CA_FILE = Path(__file__).with_name("rds-ca-bundle.pem")

# Column types for the tables in transform.COLUMNS, in the same order
SCHEMA = """
CREATE TABLE trials (
    nct_id          text PRIMARY KEY,
    title           text,
    start_year      integer,
    overall_status  text,
    why_stopped     text,
    phase           text,
    enrollment      integer,
    sponsor_name    text,
    sponsor_class   text,
    sponsor_type    text,
    outcome         text
);
CREATE TABLE conditions (
    nct_id          text NOT NULL REFERENCES trials,
    condition       text,
    condition_group text
);
CREATE TABLE interventions (
    nct_id             text NOT NULL REFERENCES trials,
    intervention_type  text,
    intervention_name  text,
    psychedelic_class  text,
    treatment_type     text
);
CREATE TABLE sites (
    nct_id   text NOT NULL REFERENCES trials,
    country  text
);
CREATE TABLE snapshot_counts (
    snapshot_date  date NOT NULL,
    metric         text NOT NULL,
    category       text,
    value          integer
);
CREATE INDEX ON conditions (nct_id);
CREATE INDEX ON interventions (nct_id);
CREATE INDEX ON sites (nct_id);
CREATE INDEX ON snapshot_counts (snapshot_date);
"""

LOAD_LOG = """
CREATE TABLE IF NOT EXISTS load_log (
    loaded_at      timestamptz NOT NULL DEFAULT now(),
    snapshot_date  date NOT NULL,
    trials         integer,
    conditions     integer,
    interventions  integer,
    sites          integer,
    seconds        numeric
)
"""

TABLES = ["trials", "conditions", "interventions", "sites"]   # parents first


def connect(host, user, password, database, port=5432):
    ctx = ssl.create_default_context(cafile=str(CA_FILE))
    return pg8000.native.Connection(user=user, password=password, host=host, port=port,
                                    database=database, ssl_context=ctx, timeout=30)


def load(con, files, snapshot_date, reader=None):
    """Replace the tables with the CSV files (a dict of name -> bytes) in one transaction.

    files holds the four tables plus "snapshot_counts" (history/counts.csv).
    reader, if given, is a role that gets SELECT on every table.
    """
    began = time.time()
    rows = {}
    con.run("BEGIN")
    try:
        con.run(LOAD_LOG)
        con.run("DROP TABLE IF EXISTS sites, interventions, conditions, trials, snapshot_counts")
        for statement in SCHEMA.split(";"):
            if statement.strip():
                con.run(statement)
        for name in TABLES + ["snapshot_counts"]:
            con.run(f"COPY {name} FROM STDIN WITH (FORMAT csv, HEADER true)",
                    stream=io.BytesIO(files[name]))
            rows[name] = con.run(f"SELECT count(*) FROM {name}")[0][0]
        con.run("INSERT INTO load_log (snapshot_date, trials, conditions, interventions, sites,"
                " seconds) VALUES (:d, :t, :c, :i, :s, :sec)",
                d=snapshot_date, t=rows["trials"], c=rows["conditions"],
                i=rows["interventions"], s=rows["sites"], sec=round(time.time() - began, 1))
        if reader:
            con.run(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{reader}"')
        con.run("COMMIT")
    except Exception:
        try:
            con.run("ROLLBACK")
        except Exception:
            pass   # the connection is gone; the server rolls back by itself
        raise
    return rows


def get(key):
    return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()


def handler(event, context):
    began = time.time()
    manifest = json.loads(get("latest/manifest.json"))
    day = manifest["snapshot_date"]
    files = {name: get(f"snapshots/{day}/{name}.csv") for name in TABLES}
    files["snapshot_counts"] = get("history/counts.csv")

    host, port, user = os.environ["DB_HOST"], int(os.environ["DB_PORT"]), os.environ["DB_USER"]
    token = boto3.client("rds").generate_db_auth_token(DBHostname=host, Port=port, DBUsername=user)
    con = connect(host, user, token, os.environ["DB_NAME"], port)
    try:
        rows = load(con, files, day, reader=os.environ.get("DB_READER"))
    finally:
        con.close()

    result = {"snapshot_date": day, "rows": rows, "seconds": round(time.time() - began, 1)}
    print(json.dumps(result))
    return result
