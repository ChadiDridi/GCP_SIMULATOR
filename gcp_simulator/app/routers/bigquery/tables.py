import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.bigquery import Dataset, Table
from gcp_simulator.app.routers.bigquery.schema_translator import bq_schema_to_pg_ddl, safe_pg_table_name

router = APIRouter()


def _table_response(t: Table) -> dict:
    return {
        "kind": "bigquery#table",
        "id": f"{t.project_id}:{t.dataset_id}.{t.table_id}",
        "tableReference": {
            "projectId": t.project_id,
            "datasetId": t.dataset_id,
            "tableId": t.table_id,
        },
        "schema": t.schema_def,
        "labels": t.labels or {},
        "creationTime": str(int(t.created_at.timestamp() * 1000)),
    }


@router.post("/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/tables")
async def create_table(
    project_id: str,
    dataset_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    table_ref = body.get("tableReference", {})
    table_id = table_ref.get("tableId", "")
    if not table_id:
        raise HTTPException(status_code=400, detail="tableId required")

    schema_def = body.get("schema", {"fields": []})

    # Verify dataset exists
    ds_result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.dataset_id == dataset_id)
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    existing = await db.execute(
        select(Table).where(
            Table.project_id == project_id,
            Table.dataset_id == dataset_id,
            Table.table_id == table_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Table {table_id} already exists")

    pg_name = safe_pg_table_name(project_id, dataset_id, table_id)

    table = Table(
        id=uuid.uuid4(),
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        schema_def=schema_def,
        pg_table_name=pg_name,
        labels=body.get("labels", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(table)
    await db.flush()

    # Create physical PostgreSQL table
    ddl = bq_schema_to_pg_ddl(pg_name, schema_def)
    await db.execute(text(ddl))

    return _table_response(table)


@router.get("/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/tables")
async def list_tables(project_id: str, dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Table).where(Table.project_id == project_id, Table.dataset_id == dataset_id)
    )
    tables = result.scalars().all()
    return {"kind": "bigquery#tableList", "tables": [_table_response(t) for t in tables]}


@router.get("/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}")
async def get_table(
    project_id: str,
    dataset_id: str,
    table_id: str,
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
    return _table_response(t)


@router.delete(
    "/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}",
    status_code=204,
)
async def delete_table(
    project_id: str,
    dataset_id: str,
    table_id: str,
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

    # Drop physical table
    await db.execute(text(f'DROP TABLE IF EXISTS bq_data."{t.pg_table_name}"'))
    await db.execute(
        delete(Table).where(
            Table.project_id == project_id,
            Table.dataset_id == dataset_id,
            Table.table_id == table_id,
        )
    )
