import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.gce import Instance

router = APIRouter()

_MACHINE_TYPES = [
    "n1-standard-1",
    "n1-standard-2",
    "n1-standard-4",
    "e2-medium",
    "n2-standard-2",
]


def _instance_response(inst: Instance) -> dict:
    return {
        "kind": "compute#instance",
        "id": str(inst.id.int),
        "name": inst.name,
        "zone": inst.zone,
        "machineType": inst.machine_type,
        "status": inst.status,
        "networkInterfaces": inst.network_interfaces or [],
        "disks": inst.disks or [],
        "metadata": inst.metadata or {},
        "labels": inst.labels or {},
        "tags": inst.tags or {},
        "selfLink": inst.self_link or "",
        "creationTimestamp": inst.created_at.isoformat() if inst.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/zones/{zone}/instances")
async def list_instances(
    project_id: str,
    zone: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Instance).where(
            Instance.project_id == project_id,
            Instance.zone == zone,
        )
    )
    instances = result.scalars().all()
    return {
        "kind": "compute#instanceList",
        "items": [_instance_response(i) for i in instances],
    }


@router.post("/compute/v1/projects/{project_id}/zones/{zone}/instances", status_code=200)
async def create_instance(
    project_id: str,
    zone: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(Instance).where(
            Instance.project_id == project_id,
            Instance.zone == zone,
            Instance.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Instance {name} already exists in zone {zone}")

    inst_id = uuid.uuid4()
    self_link = (
        f"https://www.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/instances/{name}"
    )
    inst = Instance(
        id=inst_id,
        project_id=project_id,
        zone=zone,
        name=name,
        machine_type=body.get("machineType", "n1-standard-1"),
        status="RUNNING",
        network_interfaces=body.get("networkInterfaces", []),
        disks=body.get("disks", []),
        metadata=body.get("metadata", {}),
        tags=body.get("tags", {}),
        labels=body.get("labels", {}),
        self_link=self_link,
        created_at=datetime.now(timezone.utc),
    )
    db.add(inst)
    await db.flush()
    return _instance_response(inst)


@router.get("/compute/v1/projects/{project_id}/zones/{zone}/instances/{name}")
async def get_instance(
    project_id: str,
    zone: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Instance).where(
            Instance.project_id == project_id,
            Instance.zone == zone,
            Instance.name == name,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance {name} not found in zone {zone}")
    return _instance_response(inst)


@router.delete("/compute/v1/projects/{project_id}/zones/{zone}/instances/{name}", status_code=204)
async def delete_instance(
    project_id: str,
    zone: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Instance).where(
            Instance.project_id == project_id,
            Instance.zone == zone,
            Instance.name == name,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance {name} not found in zone {zone}")
    await db.execute(
        delete(Instance).where(
            Instance.project_id == project_id,
            Instance.zone == zone,
            Instance.name == name,
        )
    )


@router.post("/compute/v1/projects/{project_id}/zones/{zone}/instances/{name}/start")
async def start_instance(
    project_id: str,
    zone: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Instance).where(
            Instance.project_id == project_id,
            Instance.zone == zone,
            Instance.name == name,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance {name} not found in zone {zone}")
    inst.status = "RUNNING"
    await db.flush()
    return _instance_response(inst)


@router.post("/compute/v1/projects/{project_id}/zones/{zone}/instances/{name}/stop")
async def stop_instance(
    project_id: str,
    zone: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Instance).where(
            Instance.project_id == project_id,
            Instance.zone == zone,
            Instance.name == name,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance {name} not found in zone {zone}")
    inst.status = "TERMINATED"
    await db.flush()
    return _instance_response(inst)


@router.get("/compute/v1/projects/{project_id}/aggregatedList/instances")
async def aggregated_list_instances(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Instance).where(Instance.project_id == project_id)
    )
    instances = result.scalars().all()

    # Group by zone
    zones: dict = {}
    for inst in instances:
        key = f"zones/{inst.zone}"
        zones.setdefault(key, []).append(_instance_response(inst))

    items = {
        zone_key: {"instances": inst_list}
        for zone_key, inst_list in zones.items()
    }
    return {
        "kind": "compute#instanceAggregatedList",
        "items": items,
    }


@router.get("/compute/v1/projects/{project_id}/zones/{zone}/machineTypes")
async def list_machine_types(project_id: str, zone: str):
    return {
        "kind": "compute#machineTypeList",
        "items": [
            {
                "kind": "compute#machineType",
                "name": mt,
                "zone": zone,
                "selfLink": (
                    f"https://www.googleapis.com/compute/v1/projects/{project_id}"
                    f"/zones/{zone}/machineTypes/{mt}"
                ),
            }
            for mt in _MACHINE_TYPES
        ],
    }
