import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.memorystore import MemorystoreInstance
from gcp_simulator.app.config import settings as app_settings
from gcp_simulator._internal.port_utils import find_free_port

router = APIRouter()


def _instance_name(project_id: str, location: str, instance_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/instances/{instance_id}"


def _instance_response(inst: MemorystoreInstance) -> dict:
    return {
        "name": _instance_name(inst.project_id, inst.location, inst.instance_id),
        "tier": inst.tier,
        "memorySizeGb": inst.memory_size_gb,
        "state": inst.state,
        "host": inst.host,
        "port": inst.port,
        "redisVersion": inst.redis_version,
        "labels": inst.labels or {},
        "createTime": inst.created_at.isoformat(),
    }


@router.post("/v1/projects/{project_id}/locations/{location}/instances")
async def create_instance(
    project_id: str, location: str, body: dict, db: AsyncSession = Depends(get_db)
):
    instance_id = body.get("instanceId", "")
    if not instance_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "instanceId required", "status": "INVALID_ARGUMENT"}},
        )

    instance_data = body.get("instance", {})

    existing = await db.execute(
        select(MemorystoreInstance).where(
            MemorystoreInstance.project_id == project_id,
            MemorystoreInstance.location == location,
            MemorystoreInstance.instance_id == instance_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Instance {instance_id} already exists")

    port = find_free_port(start=6380)
    data_dir = Path(getattr(app_settings, "data_dir", "/tmp/gcp_simulator"))

    try:
        from gcp_simulator.cli.docker_manager import docker_available, ensure_redis

        if await asyncio.to_thread(docker_available):
            await asyncio.to_thread(ensure_redis, data_dir, port)
    except Exception:
        pass

    inst = MemorystoreInstance(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        instance_id=instance_id,
        tier=instance_data.get("tier", "BASIC"),
        memory_size_gb=instance_data.get("memorySizeGb", 1),
        state="READY",
        host="127.0.0.1",
        port=port,
        redis_version=instance_data.get("redisVersion", "REDIS_7_0"),
        labels=instance_data.get("labels", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(inst)
    await db.flush()
    return _instance_response(inst)


@router.get("/v1/projects/{project_id}/locations/{location}/instances")
async def list_instances(project_id: str, location: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MemorystoreInstance).where(
            MemorystoreInstance.project_id == project_id,
            MemorystoreInstance.location == location,
        )
    )
    instances = result.scalars().all()
    return {"instances": [_instance_response(i) for i in instances]}


@router.get("/v1/projects/{project_id}/locations/{location}/instances/{instance_id}")
async def get_instance(
    project_id: str, location: str, instance_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MemorystoreInstance).where(
            MemorystoreInstance.project_id == project_id,
            MemorystoreInstance.location == location,
            MemorystoreInstance.instance_id == instance_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Instance {instance_id} not found", "status": "NOT_FOUND"}},
        )
    return _instance_response(inst)


@router.delete(
    "/v1/projects/{project_id}/locations/{location}/instances/{instance_id}", status_code=200
)
async def delete_instance(
    project_id: str, location: str, instance_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MemorystoreInstance).where(
            MemorystoreInstance.project_id == project_id,
            MemorystoreInstance.location == location,
            MemorystoreInstance.instance_id == instance_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Instance {instance_id} not found", "status": "NOT_FOUND"}},
        )

    # Attempt to stop the Redis container (best-effort)
    try:
        from gcp_simulator.cli.docker_manager import stop_redis
        await asyncio.to_thread(stop_redis, False)
    except Exception:
        pass

    await db.execute(
        delete(MemorystoreInstance).where(
            MemorystoreInstance.project_id == project_id,
            MemorystoreInstance.location == location,
            MemorystoreInstance.instance_id == instance_id,
        )
    )
    return {}
