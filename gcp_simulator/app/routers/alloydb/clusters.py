import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.alloydb import AlloyDBCluster

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/clusters"


def _cluster_name(project_id: str, location: str, cluster_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/clusters/{cluster_id}"


def _cluster_response(c: AlloyDBCluster) -> dict:
    return {
        "name": _cluster_name(c.project_id, c.location, c.cluster_id),
        "displayName": c.display_name or c.cluster_id,
        "uid": str(c.id),
        "clusterType": c.cluster_type,
        "databaseVersion": c.database_version,
        "network": c.network or "",
        "state": c.state,
        "labels": c.labels or {},
        "automatedBackupPolicy": c.automated_backup_policy or {},
        "createTime": c.created_at.isoformat() + "Z",
        "updateTime": c.updated_at.isoformat() + "Z",
    }


async def _get_cluster(
    db: AsyncSession, project_id: str, location: str, cluster_id: str
) -> AlloyDBCluster:
    result = await db.execute(
        select(AlloyDBCluster).where(
            AlloyDBCluster.project_id == project_id,
            AlloyDBCluster.location == location,
            AlloyDBCluster.cluster_id == cluster_id,
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Cluster {cluster_id} not found", "status": "NOT_FOUND"}},
        )
    return c


@router.post(_BASE)
async def create_cluster(
    project_id: str,
    location: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    cluster_id = body.get("clusterId") or body.get("cluster_id", "")
    if not cluster_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "clusterId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(AlloyDBCluster).where(
            AlloyDBCluster.project_id == project_id,
            AlloyDBCluster.location == location,
            AlloyDBCluster.cluster_id == cluster_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"Cluster {cluster_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    cluster_body = body.get("cluster", body)
    now = datetime.now(timezone.utc)
    c = AlloyDBCluster(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        cluster_id=cluster_id,
        display_name=cluster_body.get("displayName"),
        network=cluster_body.get("network"),
        database_version=cluster_body.get("databaseVersion", "POSTGRES_15"),
        cluster_type=cluster_body.get("clusterType", "PRIMARY"),
        state="READY",
        labels=cluster_body.get("labels", {}),
        automated_backup_policy=cluster_body.get("automatedBackupPolicy", {}),
        created_at=now,
        updated_at=now,
    )
    db.add(c)
    await db.flush()
    return _cluster_response(c)


@router.get(_BASE)
async def list_clusters(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBCluster).where(
            AlloyDBCluster.project_id == project_id,
            AlloyDBCluster.location == location,
        )
    )
    clusters = result.scalars().all()
    return {"clusters": [_cluster_response(c) for c in clusters]}


@router.get(_BASE + "/{cluster_id}")
async def get_cluster(
    project_id: str,
    location: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    return _cluster_response(await _get_cluster(db, project_id, location, cluster_id))


@router.patch(_BASE + "/{cluster_id}")
async def update_cluster(
    project_id: str,
    location: str,
    cluster_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    c = await _get_cluster(db, project_id, location, cluster_id)
    if "displayName" in body:
        c.display_name = body["displayName"]
    if "labels" in body:
        c.labels = body["labels"]
    if "automatedBackupPolicy" in body:
        c.automated_backup_policy = body["automatedBackupPolicy"]
    if "network" in body:
        c.network = body["network"]
    c.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _cluster_response(c)


@router.delete(_BASE + "/{cluster_id}", status_code=200)
async def delete_cluster(
    project_id: str,
    location: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_cluster(db, project_id, location, cluster_id)
    await db.execute(
        delete(AlloyDBCluster).where(
            AlloyDBCluster.project_id == project_id,
            AlloyDBCluster.location == location,
            AlloyDBCluster.cluster_id == cluster_id,
        )
    )
    return {}
