import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.alloydb import AlloyDBDatabase

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/clusters/{cluster_id}/databases"


def _db_name(project_id: str, location: str, cluster_id: str, database_name: str) -> str:
    return f"projects/{project_id}/locations/{location}/clusters/{cluster_id}/databases/{database_name}"


def _db_response(d: AlloyDBDatabase) -> dict:
    return {
        "name": _db_name(d.project_id, d.location, d.cluster_id, d.database_name),
        "charset": d.charset,
        "collation": d.collation,
        "createTime": d.created_at.isoformat() + "Z",
    }


@router.post(_BASE)
async def create_database(
    project_id: str,
    location: str,
    cluster_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    database_name = body.get("databaseId") or body.get("database_name") or body.get("name", "")
    if not database_name:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "databaseId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(AlloyDBDatabase).where(
            AlloyDBDatabase.project_id == project_id,
            AlloyDBDatabase.location == location,
            AlloyDBDatabase.cluster_id == cluster_id,
            AlloyDBDatabase.database_name == database_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"Database {database_name} already exists", "status": "ALREADY_EXISTS"}},
        )

    db_body = body.get("database", body)
    d = AlloyDBDatabase(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        cluster_id=cluster_id,
        database_name=database_name,
        charset=db_body.get("charset", "UTF8"),
        collation=db_body.get("collation", "en_US.UTF8"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(d)
    await db.flush()
    return _db_response(d)


@router.get(_BASE)
async def list_databases(
    project_id: str,
    location: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBDatabase).where(
            AlloyDBDatabase.project_id == project_id,
            AlloyDBDatabase.location == location,
            AlloyDBDatabase.cluster_id == cluster_id,
        )
    )
    databases = result.scalars().all()
    return {"databases": [_db_response(d) for d in databases]}


@router.get(_BASE + "/{database_name}")
async def get_database(
    project_id: str,
    location: str,
    cluster_id: str,
    database_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBDatabase).where(
            AlloyDBDatabase.project_id == project_id,
            AlloyDBDatabase.location == location,
            AlloyDBDatabase.cluster_id == cluster_id,
            AlloyDBDatabase.database_name == database_name,
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Database {database_name} not found", "status": "NOT_FOUND"}},
        )
    return _db_response(d)


@router.delete(_BASE + "/{database_name}", status_code=200)
async def delete_database(
    project_id: str,
    location: str,
    cluster_id: str,
    database_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBDatabase).where(
            AlloyDBDatabase.project_id == project_id,
            AlloyDBDatabase.location == location,
            AlloyDBDatabase.cluster_id == cluster_id,
            AlloyDBDatabase.database_name == database_name,
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Database {database_name} not found", "status": "NOT_FOUND"}},
        )
    await db.execute(
        delete(AlloyDBDatabase).where(AlloyDBDatabase.id == d.id)
    )
    return {}
