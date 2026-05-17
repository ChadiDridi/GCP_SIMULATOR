import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.dns import ManagedZone

router = APIRouter()


def _zone_response(zone: ManagedZone) -> dict:
    return {
        "kind": "dns#managedZone",
        "id": str(zone.id),
        "name": zone.name,
        "dnsName": zone.dns_name or "",
        "description": zone.description or "",
        "visibility": zone.visibility,
        "dnssecConfig": zone.dnssec_config or {},
        "creationTime": zone.created_at.isoformat() if zone.created_at else None,
    }


@router.get("/dns/v1/projects/{project_id}/managedZones")
async def list_zones(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManagedZone).where(ManagedZone.project_id == project_id)
    )
    zones = result.scalars().all()
    return {"kind": "dns#managedZonesListResponse", "managedZones": [_zone_response(z) for z in zones]}


@router.post("/dns/v1/projects/{project_id}/managedZones", status_code=200)
async def create_zone(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(ManagedZone).where(
            ManagedZone.project_id == project_id, ManagedZone.name == name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"ManagedZone {name} already exists")

    zone = ManagedZone(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        dns_name=body.get("dnsName"),
        description=body.get("description"),
        visibility=body.get("visibility", "public"),
        dnssec_config=body.get("dnssecConfig", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(zone)
    await db.flush()
    return _zone_response(zone)


@router.get("/dns/v1/projects/{project_id}/managedZones/{zone_name}")
async def get_zone(project_id: str, zone_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManagedZone).where(
            ManagedZone.project_id == project_id, ManagedZone.name == zone_name
        )
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail=f"ManagedZone {zone_name} not found")
    return _zone_response(zone)


@router.patch("/dns/v1/projects/{project_id}/managedZones/{zone_name}")
async def patch_zone(
    project_id: str,
    zone_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ManagedZone).where(
            ManagedZone.project_id == project_id, ManagedZone.name == zone_name
        )
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail=f"ManagedZone {zone_name} not found")

    body = await request.json()
    if "description" in body:
        zone.description = body["description"]
    if "dnssecConfig" in body:
        zone.dnssec_config = body["dnssecConfig"]
    if "visibility" in body:
        zone.visibility = body["visibility"]
    await db.flush()
    return _zone_response(zone)


@router.delete("/dns/v1/projects/{project_id}/managedZones/{zone_name}", status_code=204)
async def delete_zone(project_id: str, zone_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManagedZone).where(
            ManagedZone.project_id == project_id, ManagedZone.name == zone_name
        )
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail=f"ManagedZone {zone_name} not found")
    await db.execute(
        delete(ManagedZone).where(
            ManagedZone.project_id == project_id, ManagedZone.name == zone_name
        )
    )
