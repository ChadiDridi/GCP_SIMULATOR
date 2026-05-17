"""Translate BigQuery TableSchema to PostgreSQL DDL and back."""

_BQ_TO_PG = {
    "STRING": "TEXT",
    "BYTES": "BYTEA",
    "INTEGER": "BIGINT",
    "INT64": "BIGINT",
    "FLOAT": "DOUBLE PRECISION",
    "FLOAT64": "DOUBLE PRECISION",
    "NUMERIC": "NUMERIC",
    "BIGNUMERIC": "NUMERIC",
    "BOOLEAN": "BOOLEAN",
    "BOOL": "BOOLEAN",
    "TIMESTAMP": "TIMESTAMPTZ",
    "DATE": "DATE",
    "TIME": "TIME",
    "DATETIME": "TIMESTAMP",
    "RECORD": "JSONB",
    "STRUCT": "JSONB",
    "JSON": "JSONB",
    "GEOGRAPHY": "TEXT",
}


def bq_schema_to_pg_ddl(pg_table_name: str, schema_def: dict) -> str:
    """Return CREATE TABLE statement for bq_data schema."""
    fields = schema_def.get("fields", [])
    columns = []
    for field in fields:
        col_name = _safe_col(field["name"])
        bq_type = field.get("type", "STRING").upper()
        pg_type = _BQ_TO_PG.get(bq_type, "TEXT")
        mode = field.get("mode", "NULLABLE").upper()
        null_clause = " NOT NULL" if mode == "REQUIRED" else ""
        columns.append(f'    "{col_name}" {pg_type}{null_clause}')

    cols_sql = ",\n".join(columns)
    return f'CREATE TABLE IF NOT EXISTS bq_data."{pg_table_name}" (\n{cols_sql}\n)'


def bq_row_to_pg_values(row: dict, schema_def: dict) -> tuple[list[str], list]:
    """Convert a BQ insertAll row to column names + values for INSERT."""
    fields = schema_def.get("fields", [])
    json_row = row.get("json", row)
    col_names = []
    values = []
    for field in fields:
        name = field["name"]
        col_names.append(f'"{_safe_col(name)}"')
        values.append(json_row.get(name))
    return col_names, values


def pg_rows_to_bq_result(rows, col_names: list[str]) -> dict:
    """Convert asyncpg row results to BigQuery queryResponse format."""
    schema_fields = [{"name": c, "type": "STRING", "mode": "NULLABLE"} for c in col_names]
    result_rows = []
    for row in rows:
        f = []
        for val in row:
            f.append({"v": str(val) if val is not None else None})
        result_rows.append({"f": f})
    return {
        "schema": {"fields": schema_fields},
        "rows": result_rows,
        "totalRows": str(len(result_rows)),
    }


def _safe_col(name: str) -> str:
    return name.replace('"', '""')


def safe_pg_table_name(project_id: str, dataset_id: str, table_id: str) -> str:
    """Create a safe, unique PostgreSQL table name."""
    parts = [project_id, dataset_id, table_id]
    combined = "__".join(p.replace("-", "_").replace(".", "_")[:40] for p in parts)
    return combined[:63]
