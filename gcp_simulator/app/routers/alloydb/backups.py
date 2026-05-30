import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.alloydb import AlloyDBBackup

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/backups"


def _backup_name(project_id: str, location: str, backup_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/backups/{backup_id}"


def _backup_response(b: AlloyDBBackup) -> dict:
    return {
        "name": _backup_name(b.project_id, b.location, b.backup_id),
        "displayName": b.display_name or b.backup_id,
        "uid": str(b.id),
        "clusterName": b.cluster_name,
        "databaseVersion": b.database_version,
        "backupType": b.backup_type,
        "state": b.state,
        "sizeBytes": str(b.size_bytes) if b.size_bytes else "0",
        "labels": b.labels or {},
        "expireTime": b.expire_time.isoformat() + "Z" if b.expire_time else None,
        "createTime": b.created_at.isoformat() + "Z",
        "updateTime": b.updated_at.isoformat() + "Z",
    }


@router.post(_BASE)
async def create_backup(
    project_id: str,
    location: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    backup_id = body.get("backupId") or body.get("backup_id", "")
    if not backup_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "backupId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(AlloyDBBackup).where(
            AlloyDBBackup.project_id == project_id,
            AlloyDBBackup.location == location,
            AlloyDBBackup.backup_id == backup_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"Backup {backup_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    backup_body = body.get("backup", body)
    cluster_name = backup_body.get("clusterName", "")
    if not cluster_name:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "backup.clusterName is required", "status": "INVALID_ARGUMENT"}},
        )

    now = datetime.now(timezone.utc)
    b = AlloyDBBackup(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        backup_id=backup_id,
        display_name=backup_body.get("displayName"),
        cluster_name=cluster_name,
        database_version=backup_body.get("databaseVersion", "POSTGRES_15"),
        backup_type=backup_body.get("backupType", "ON_DEMAND"),
        state="READY",
        size_bytes=backup_body.get("sizeBytes"),
        labels=backup_body.get("labels", {}),
        expire_time=now + timedelta(days=14),
        created_at=now,
        updated_at=now,
    )
    db.add(b)
    await db.flush()
    return _backup_response(b)


@router.get(_BASE)
async def list_backups(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBBackup).where(
            AlloyDBBackup.project_id == project_id,
            AlloyDBBackup.location == location,
        )
    )
    backups = result.scalars().all()
    return {"backups": [_backup_response(b) for b in backups]}


@router.get(_BASE + "/{backup_id}")
async def get_backup(
    project_id: str,
    location: str,
    backup_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBBackup).where(
            AlloyDBBackup.project_id == project_id,
            AlloyDBBackup.location == location,
            AlloyDBBackup.backup_id == backup_id,
        )
    )
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Backup {backup_id} not found", "status": "NOT_FOUND"}},
        )
    return _backup_response(b)


@router.patch(_BASE + "/{backup_id}")
async def update_backup(
    project_id: str,
    location: str,
    backup_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBBackup).where(
            AlloyDBBackup.project_id == project_id,
            AlloyDBBackup.location == location,
            AlloyDBBackup.backup_id == backup_id,
        )
    )
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Backup {backup_id} not found", "status": "NOT_FOUND"}},
        )
    if "displayName" in body:
        b.display_name = body["displayName"]
    if "labels" in body:
        b.labels = body["labels"]
    b.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _backup_response(b)


@router.delete(_BASE + "/{backup_id}", status_code=200)
async def delete_backup(
    project_id: str,
    location: str,
    backup_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBBackup).where(
            AlloyDBBackup.project_id == project_id,
            AlloyDBBackup.location == location,
            AlloyDBBackup.backup_id == backup_id,
        )
    )
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Backup {backup_id} not found", "status": "NOT_FOUND"}},
        )
    await db.execute(delete(AlloyDBBackup).where(AlloyDBBackup.id == b.id))
    return {}
