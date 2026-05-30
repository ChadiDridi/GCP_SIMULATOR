import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.alloydb import AlloyDBInstance

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/clusters/{cluster_id}/instances"


def _instance_name(project_id: str, location: str, cluster_id: str, instance_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/clusters/{cluster_id}/instances/{instance_id}"


def _instance_response(i: AlloyDBInstance) -> dict:
    return {
        "name": _instance_name(i.project_id, i.location, i.cluster_id, i.instance_id),
        "displayName": i.display_name or i.instance_id,
        "uid": str(i.id),
        "instanceType": i.instance_type,
        "machineConfig": {"cpuCount": i.cpu_count},
        "state": i.state,
        "ipAddress": i.ip_address or "127.0.0.1",
        "publicIpAddress": i.public_ip_address,
        "databaseFlags": i.database_flags or {},
        "labels": i.labels or {},
        "createTime": i.created_at.isoformat() + "Z",
        "updateTime": i.updated_at.isoformat() + "Z",
    }


async def _get_instance(
    db: AsyncSession,
    project_id: str,
    location: str,
    cluster_id: str,
    instance_id: str,
) -> AlloyDBInstance:
    result = await db.execute(
        select(AlloyDBInstance).where(
            AlloyDBInstance.project_id == project_id,
            AlloyDBInstance.location == location,
            AlloyDBInstance.cluster_id == cluster_id,
            AlloyDBInstance.instance_id == instance_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Instance {instance_id} not found", "status": "NOT_FOUND"}},
        )
    return inst


@router.post(_BASE)
async def create_instance(
    project_id: str,
    location: str,
    cluster_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    instance_id = body.get("instanceId") or body.get("instance_id", "")
    if not instance_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "instanceId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(AlloyDBInstance).where(
            AlloyDBInstance.project_id == project_id,
            AlloyDBInstance.location == location,
            AlloyDBInstance.cluster_id == cluster_id,
            AlloyDBInstance.instance_id == instance_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"Instance {instance_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    instance_body = body.get("instance", body)
    machine_config = instance_body.get("machineConfig", {})
    now = datetime.now(timezone.utc)
    inst = AlloyDBInstance(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        cluster_id=cluster_id,
        instance_id=instance_id,
        display_name=instance_body.get("displayName"),
        instance_type=instance_body.get("instanceType", "PRIMARY"),
        cpu_count=machine_config.get("cpuCount", 2),
        state="READY",
        ip_address="127.0.0.1",
        public_ip_address=None,
        database_flags=instance_body.get("databaseFlags", {}),
        labels=instance_body.get("labels", {}),
        created_at=now,
        updated_at=now,
    )
    db.add(inst)
    await db.flush()
    return _instance_response(inst)


@router.get(_BASE)
async def list_instances(
    project_id: str,
    location: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBInstance).where(
            AlloyDBInstance.project_id == project_id,
            AlloyDBInstance.location == location,
            AlloyDBInstance.cluster_id == cluster_id,
        )
    )
    instances = result.scalars().all()
    return {"instances": [_instance_response(i) for i in instances]}


@router.get(_BASE + "/{instance_id}")
async def get_instance(
    project_id: str,
    location: str,
    cluster_id: str,
    instance_id: str,
    db: AsyncSession = Depends(get_db),
):
    return _instance_response(
        await _get_instance(db, project_id, location, cluster_id, instance_id)
    )


@router.patch(_BASE + "/{instance_id}")
async def update_instance(
    project_id: str,
    location: str,
    cluster_id: str,
    instance_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    inst = await _get_instance(db, project_id, location, cluster_id, instance_id)
    if "displayName" in body:
        inst.display_name = body["displayName"]
    if "labels" in body:
        inst.labels = body["labels"]
    if "databaseFlags" in body:
        inst.database_flags = body["databaseFlags"]
    if "machineConfig" in body:
        inst.cpu_count = body["machineConfig"].get("cpuCount", inst.cpu_count)
    inst.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _instance_response(inst)


@router.delete(_BASE + "/{instance_id}", status_code=200)
async def delete_instance(
    project_id: str,
    location: str,
    cluster_id: str,
    instance_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_instance(db, project_id, location, cluster_id, instance_id)
    await db.execute(
        delete(AlloyDBInstance).where(
            AlloyDBInstance.project_id == project_id,
            AlloyDBInstance.location == location,
            AlloyDBInstance.cluster_id == cluster_id,
            AlloyDBInstance.instance_id == instance_id,
        )
    )
    return {}
