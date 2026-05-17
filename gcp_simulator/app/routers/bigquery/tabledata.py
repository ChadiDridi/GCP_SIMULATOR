from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.bigquery import Table
from gcp_simulator.app.routers.bigquery.schema_translator import bq_row_to_pg_values
from gcp_simulator.app.schemas.bigquery import InsertAllRequest

router = APIRouter()


@router.post(
    "/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}/insertAll"
)
async def insert_all(
    project_id: str,
    dataset_id: str,
    table_id: str,
    body: InsertAllRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Table).where(
            Table.project_id == project_id,
            Table.dataset_id == dataset_id,
            Table.table_id == table_id,
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail=f"Table {table_id} not found")

    insert_errors = []
    for idx, row in enumerate(body.rows):
        try:
            col_names, values = bq_row_to_pg_values(row, t.schema_def)
            if not col_names:
                continue
            placeholders = ", ".join(f":v{i}" for i in range(len(values)))
            cols = ", ".join(col_names)
            params = {f"v{i}": v for i, v in enumerate(values)}
            stmt = text(f'INSERT INTO bq_data."{t.pg_table_name}" ({cols}) VALUES ({placeholders})')
            await db.execute(stmt, params)
        except Exception as e:
            if not body.skipInvalidRows:
                insert_errors.append({"index": idx, "errors": [{"message": str(e)}]})

    await db.flush()
    return {"kind": "bigquery#tableDataInsertAllResponse", "insertErrors": insert_errors}
