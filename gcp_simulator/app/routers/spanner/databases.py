import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.spanner import SpannerDatabase

router = APIRouter()


def _db_response(d: SpannerDatabase) -> dict:
    return {
        "name": f"projects/{d.project_id}/instances/{d.instance_id}/databases/{d.database_id}",
        "state": d.state,
        "createTime": d.created_at.isoformat(),
        "extraStatements": d.ddl_statements or [],
    }


@router.post("/v1/projects/{project_id}/instances/{instance_id}/databases")
async def create_database(
    project_id: str, instance_id: str, body: dict, db: AsyncSession = Depends(get_db)
):
    database_id = body.get("createStatement", "").replace("CREATE DATABASE ", "").strip("`'\"")
    if not database_id:
        database_id = body.get("databaseId", "")
    if not database_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "databaseId required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(SpannerDatabase).where(
            SpannerDatabase.project_id == project_id,
            SpannerDatabase.instance_id == instance_id,
            SpannerDatabase.database_id == database_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Database {database_id} already exists")

    d = SpannerDatabase(
        id=uuid.uuid4(),
        project_id=project_id,
        instance_id=instance_id,
        database_id=database_id,
        state="READY",
        ddl_statements=body.get("extraStatements", []),
        created_at=datetime.now(timezone.utc),
    )
    db.add(d)
    await db.flush()
    return _db_response(d)


@router.get("/v1/projects/{project_id}/instances/{instance_id}/databases")
async def list_databases(project_id: str, instance_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SpannerDatabase).where(
            SpannerDatabase.project_id == project_id,
            SpannerDatabase.instance_id == instance_id,
        )
    )
    databases = result.scalars().all()
    return {"databases": [_db_response(d) for d in databases]}


@router.get("/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}")
async def get_database(
    project_id: str, instance_id: str, database_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SpannerDatabase).where(
            SpannerDatabase.project_id == project_id,
            SpannerDatabase.instance_id == instance_id,
            SpannerDatabase.database_id == database_id,
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Database {database_id} not found", "status": "NOT_FOUND"}},
        )
    return _db_response(d)


@router.delete(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}", status_code=200
)
async def delete_database(
    project_id: str, instance_id: str, database_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SpannerDatabase).where(
            SpannerDatabase.project_id == project_id,
            SpannerDatabase.instance_id == instance_id,
            SpannerDatabase.database_id == database_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Database {database_id} not found", "status": "NOT_FOUND"}},
        )
    await db.execute(
        delete(SpannerDatabase).where(
            SpannerDatabase.project_id == project_id,
            SpannerDatabase.instance_id == instance_id,
            SpannerDatabase.database_id == database_id,
        )
    )
    return {}
