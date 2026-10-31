"""Write the four tables as Parquet files for Athena.

Needs pyarrow. On Lambda it comes from the AWS SDK for pandas layer
(PandasLayerArn in template.yaml); on your own computer, pip install pyarrow.

SCHEMAS uses the Glue/Athena type names, and the Glue tables in template.yaml
must list the same columns in the same order.
"""

import io

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMAS = {
    "trials": [("nct_id", "string"), ("title", "string"), ("start_year", "int"),
               ("overall_status", "string"), ("why_stopped", "string"), ("phase", "string"),
               ("enrollment", "bigint"), ("sponsor_name", "string"), ("sponsor_class", "string"),
               ("sponsor_type", "string"), ("outcome", "string")],
    "conditions": [("nct_id", "string"), ("condition", "string"), ("condition_group", "string")],
    "interventions": [("nct_id", "string"), ("intervention_type", "string"),
                      ("intervention_name", "string"), ("psychedelic_class", "string"),
                      ("treatment_type", "string")],
    "sites": [("nct_id", "string"), ("country", "string")],
}

ARROW = {"string": pa.string(), "int": pa.int32(), "bigint": pa.int64()}


def _value(v, kind):
    # Empty strings become nulls: CSV files cannot tell the two apart, and the
    # queries test psychedelic_class IS NOT NULL and why_stopped for blanks.
    if v is None or v == "":
        return None
    if kind == "string":
        return str(v)
    return int(float(v))   # pandas wrote enrollment as "120.0" in the published CSV files


def to_parquet(rows, name):
    """Return one table as Parquet bytes (Snappy-compressed)."""
    schema = pa.schema([(col, ARROW[kind]) for col, kind in SCHEMAS[name]])
    columns = {col: [_value(r.get(col), kind) for r in rows] for col, kind in SCHEMAS[name]}
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pydict(columns, schema=schema), buf, compression="snappy")
    return buf.getvalue()
