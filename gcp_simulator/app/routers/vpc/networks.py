import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.vpc import Network

router = APIRouter()


def _network_response(net: Network) -> dict:
    return {
        "kind": "compute#network",
        "id": str(net.id),
        "name": net.name,
        "autoCreateSubnetworks": net.auto_create_subnetworks,
        "routingConfig": {"routingMode": net.routing_mode},
        "description": net.description or "",
        "labels": net.labels or {},
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{net.project_id}/global/networks/{net.name}"
        ),
        "creationTimestamp": net.created_at.isoformat() if net.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/global/networks")
async def list_networks(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Network).where(Network.project_id == project_id))
    networks = result.scalars().all()
    return {
        "kind": "compute#networkList",
        "items": [_network_response(n) for n in networks],
    }


@router.post("/compute/v1/projects/{project_id}/global/networks", status_code=200)
async def create_network(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(Network).where(Network.project_id == project_id, Network.name == name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Network {name} already exists")

    net = Network(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        auto_create_subnetworks=body.get("autoCreateSubnetworks", True),
        routing_mode=body.get("routingConfig", {}).get("routingMode", "REGIONAL"),
        description=body.get("description"),
        labels=body.get("labels", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(net)
    await db.flush()
    return _network_response(net)


@router.get("/compute/v1/projects/{project_id}/global/networks/{name}")
async def get_network(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Network).where(Network.project_id == project_id, Network.name == name)
    )
    net = result.scalar_one_or_none()
    if not net:
        raise HTTPException(status_code=404, detail=f"Network {name} not found")
    return _network_response(net)


@router.patch("/compute/v1/projects/{project_id}/global/networks/{name}")
async def patch_network(
    project_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Network).where(Network.project_id == project_id, Network.name == name)
    )
    net = result.scalar_one_or_none()
    if not net:
        raise HTTPException(status_code=404, detail=f"Network {name} not found")

    body = await request.json()
    if "autoCreateSubnetworks" in body:
        net.auto_create_subnetworks = body["autoCreateSubnetworks"]
    if "routingConfig" in body:
        net.routing_mode = body["routingConfig"].get("routingMode", net.routing_mode)
    if "description" in body:
        net.description = body["description"]
    if "labels" in body:
        net.labels = body["labels"]
    await db.flush()
    return _network_response(net)


@router.delete("/compute/v1/projects/{project_id}/global/networks/{name}", status_code=204)
async def delete_network(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Network).where(Network.project_id == project_id, Network.name == name)
    )
    net = result.scalar_one_or_none()
    if not net:
        raise HTTPException(status_code=404, detail=f"Network {name} not found")
    await db.execute(
        delete(Network).where(Network.project_id == project_id, Network.name == name)
    )
