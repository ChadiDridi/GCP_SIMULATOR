import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.bigtable import BigtableTable

router = APIRouter()


def _table_name(project_id: str, instance_id: str, table_id: str) -> str:
    return f"projects/{project_id}/instances/{instance_id}/tables/{table_id}"


def _table_response(t: BigtableTable) -> dict:
    return {
        "name": _table_name(t.project_id, t.instance_id, t.table_id),
        "columnFamilies": t.column_families or {},
    }


@router.post("/v2/projects/{project_id}/instances/{instance_id}/tables")
async def create_table(
    project_id: str, instance_id: str, body: dict, db: AsyncSession = Depends(get_db)
):
    table_id = body.get("tableId", "")
    if not table_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "tableId required", "status": "INVALID_ARGUMENT"}},
        )

    table_data = body.get("table", {})
    column_families = table_data.get("columnFamilies", {})

    existing = await db.execute(
        select(BigtableTable).where(
            BigtableTable.project_id == project_id,
            BigtableTable.instance_id == instance_id,
            BigtableTable.table_id == table_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Table {table_id} already exists")

    t = BigtableTable(
        id=uuid.uuid4(),
        project_id=project_id,
        instance_id=instance_id,
        table_id=table_id,
        column_families=column_families,
        created_at=datetime.now(timezone.utc),
    )
    db.add(t)
    await db.flush()
    return _table_response(t)


@router.get("/v2/projects/{project_id}/instances/{instance_id}/tables")
async def list_tables(project_id: str, instance_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BigtableTable).where(
            BigtableTable.project_id == project_id,
            BigtableTable.instance_id == instance_id,
        )
    )
    tables = result.scalars().all()
    return {"tables": [_table_response(t) for t in tables]}


@router.get("/v2/projects/{project_id}/instances/{instance_id}/tables/{table_id}")
async def get_table(
    project_id: str, instance_id: str, table_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(BigtableTable).where(
            BigtableTable.project_id == project_id,
            BigtableTable.instance_id == instance_id,
            BigtableTable.table_id == table_id,
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Table {table_id} not found", "status": "NOT_FOUND"}},
        )
    return _table_response(t)


@router.delete(
    "/v2/projects/{project_id}/instances/{instance_id}/tables/{table_id}", status_code=200
)
async def delete_table(
    project_id: str, instance_id: str, table_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(BigtableTable).where(
            BigtableTable.project_id == project_id,
            BigtableTable.instance_id == instance_id,
            BigtableTable.table_id == table_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Table {table_id} not found", "status": "NOT_FOUND"}},
        )
    await db.execute(
        delete(BigtableTable).where(
            BigtableTable.project_id == project_id,
            BigtableTable.instance_id == instance_id,
            BigtableTable.table_id == table_id,
        )
    )
    return {}


@router.post(
    "/v2/projects/{project_id}/instances/{instance_id}/tables/{table_id}:modifyColumnFamilies"
)
async def modify_column_families(
    project_id: str, instance_id: str, table_id: str, body: dict, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(BigtableTable).where(
            BigtableTable.project_id == project_id,
            BigtableTable.instance_id == instance_id,
            BigtableTable.table_id == table_id,
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Table {table_id} not found", "status": "NOT_FOUND"}},
        )

    modifications = body.get("modifications", [])
    families = dict(t.column_families or {})

    for mod in modifications:
        if "create" in mod:
            family_id = mod.get("id", "")
            families[family_id] = mod["create"]
        elif "update" in mod:
            family_id = mod.get("id", "")
            families[family_id] = mod["update"]
        elif "drop" in mod:
            family_id = mod.get("id", "")
            families.pop(family_id, None)

    t.column_families = families
    await db.flush()
    return _table_response(t)
