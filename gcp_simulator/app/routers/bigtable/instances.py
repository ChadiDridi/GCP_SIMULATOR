import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.bigtable import BigtableInstance

router = APIRouter()


def _instance_response(inst: BigtableInstance) -> dict:
    return {
        "name": f"projects/{inst.project_id}/instances/{inst.instance_id}",
        "displayName": inst.display_name,
        "state": inst.state,
        "type": inst.type,
        "labels": inst.labels or {},
    }


@router.post("/v2/projects/{project_id}/instances")
async def create_instance(project_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    instance_id = body.get("instanceId", "")
    if not instance_id:
        raise HTTPException(status_code=400, detail={"error": {"code": 400, "message": "instanceId required", "status": "INVALID_ARGUMENT"}})

    instance_data = body.get("instance", {})
    existing = await db.execute(
        select(BigtableInstance).where(
            BigtableInstance.project_id == project_id,
            BigtableInstance.instance_id == instance_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Instance {instance_id} already exists")

    inst = BigtableInstance(
        id=uuid.uuid4(),
        project_id=project_id,
        instance_id=instance_id,
        display_name=instance_data.get("displayName", instance_id),
        type=instance_data.get("type", "PRODUCTION"),
        state="READY",
        labels=instance_data.get("labels", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(inst)
    await db.flush()
    return _instance_response(inst)


@router.get("/v2/projects/{project_id}/instances")
async def list_instances(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BigtableInstance).where(BigtableInstance.project_id == project_id)
    )
    instances = result.scalars().all()
    return {"instances": [_instance_response(i) for i in instances]}


@router.get("/v2/projects/{project_id}/instances/{instance_id}")
async def get_instance(project_id: str, instance_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BigtableInstance).where(
            BigtableInstance.project_id == project_id,
            BigtableInstance.instance_id == instance_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Instance {instance_id} not found", "status": "NOT_FOUND"}},
        )
    return _instance_response(inst)


@router.delete("/v2/projects/{project_id}/instances/{instance_id}", status_code=200)
async def delete_instance(project_id: str, instance_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BigtableInstance).where(
            BigtableInstance.project_id == project_id,
            BigtableInstance.instance_id == instance_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Instance {instance_id} not found", "status": "NOT_FOUND"}},
        )
    await db.execute(
        delete(BigtableInstance).where(
            BigtableInstance.project_id == project_id,
            BigtableInstance.instance_id == instance_id,
        )
    )
    return {}
