import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.dns import ManagedZone, RecordSet

router = APIRouter()


def _rrset_response(rs: RecordSet) -> dict:
    return {
        "kind": "dns#resourceRecordSet",
        "id": str(rs.id),
        "name": rs.name,
        "type": rs.type,
        "ttl": rs.ttl,
        "rrdatas": rs.rrdatas or [],
    }


async def _get_zone_or_404(
    project_id: str, zone_name: str, db: AsyncSession
) -> ManagedZone:
    result = await db.execute(
        select(ManagedZone).where(
            ManagedZone.project_id == project_id, ManagedZone.name == zone_name
        )
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail=f"ManagedZone {zone_name} not found")
    return zone


@router.get("/dns/v1/projects/{project_id}/managedZones/{zone_name}/rrsets")
async def list_rrsets(
    project_id: str,
    zone_name: str,
    db: AsyncSession = Depends(get_db),
):
    zone = await _get_zone_or_404(project_id, zone_name, db)
    result = await db.execute(select(RecordSet).where(RecordSet.zone_id == zone.id))
    rrsets = result.scalars().all()
    return {
        "kind": "dns#resourceRecordSetsListResponse",
        "rrsets": [_rrset_response(r) for r in rrsets],
    }


@router.post("/dns/v1/projects/{project_id}/managedZones/{zone_name}/rrsets", status_code=200)
async def create_rrset(
    project_id: str,
    zone_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    zone = await _get_zone_or_404(project_id, zone_name, db)
    body = await request.json()
    name = body.get("name")
    rtype = body.get("type")
    if not name or not rtype:
        raise HTTPException(status_code=400, detail="name and type are required")

    existing = await db.execute(
        select(RecordSet).where(
            RecordSet.zone_id == zone.id,
            RecordSet.name == name,
            RecordSet.type == rtype,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"RecordSet {name}/{rtype} already exists")

    rs = RecordSet(
        id=uuid.uuid4(),
        zone_id=zone.id,
        name=name,
        type=rtype,
        ttl=body.get("ttl", 300),
        rrdatas=body.get("rrdatas", []),
        created_at=datetime.now(timezone.utc),
    )
    db.add(rs)
    await db.flush()
    return _rrset_response(rs)


@router.get("/dns/v1/projects/{project_id}/managedZones/{zone_name}/rrsets/{name}/{rtype}")
async def get_rrset(
    project_id: str,
    zone_name: str,
    name: str,
    rtype: str,
    db: AsyncSession = Depends(get_db),
):
    zone = await _get_zone_or_404(project_id, zone_name, db)
    result = await db.execute(
        select(RecordSet).where(
            RecordSet.zone_id == zone.id,
            RecordSet.name == name,
            RecordSet.type == rtype,
        )
    )
    rs = result.scalar_one_or_none()
    if not rs:
        raise HTTPException(status_code=404, detail=f"RecordSet {name}/{rtype} not found")
    return _rrset_response(rs)


@router.delete(
    "/dns/v1/projects/{project_id}/managedZones/{zone_name}/rrsets/{name}/{rtype}",
    status_code=204,
)
async def delete_rrset(
    project_id: str,
    zone_name: str,
    name: str,
    rtype: str,
    db: AsyncSession = Depends(get_db),
):
    zone = await _get_zone_or_404(project_id, zone_name, db)
    result = await db.execute(
        select(RecordSet).where(
            RecordSet.zone_id == zone.id,
            RecordSet.name == name,
            RecordSet.type == rtype,
        )
    )
    rs = result.scalar_one_or_none()
    if not rs:
        raise HTTPException(status_code=404, detail=f"RecordSet {name}/{rtype} not found")
    await db.execute(
        delete(RecordSet).where(
            RecordSet.zone_id == zone.id,
            RecordSet.name == name,
            RecordSet.type == rtype,
        )
    )


@router.post("/dns/v1/projects/{project_id}/managedZones/{zone_name}/changes")
async def apply_changes(
    project_id: str,
    zone_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Batch add/delete rrsets (DNS Changes API)."""
    zone = await _get_zone_or_404(project_id, zone_name, db)
    body = await request.json()
    additions = body.get("additions", [])
    deletions = body.get("deletions", [])
    now = datetime.now(timezone.utc)

    added = []
    for item in additions:
        name = item.get("name")
        rtype = item.get("type")
        if not name or not rtype:
            continue
        existing = await db.execute(
            select(RecordSet).where(
                RecordSet.zone_id == zone.id,
                RecordSet.name == name,
                RecordSet.type == rtype,
            )
        )
        rs = existing.scalar_one_or_none()
        if rs:
            rs.ttl = item.get("ttl", rs.ttl)
            rs.rrdatas = item.get("rrdatas", rs.rrdatas)
        else:
            rs = RecordSet(
                id=uuid.uuid4(),
                zone_id=zone.id,
                name=name,
                type=rtype,
                ttl=item.get("ttl", 300),
                rrdatas=item.get("rrdatas", []),
                created_at=now,
            )
            db.add(rs)
        added.append(item)

    deleted = []
    for item in deletions:
        name = item.get("name")
        rtype = item.get("type")
        if not name or not rtype:
            continue
        await db.execute(
            delete(RecordSet).where(
                RecordSet.zone_id == zone.id,
                RecordSet.name == name,
                RecordSet.type == rtype,
            )
        )
        deleted.append(item)

    await db.flush()
    return {
        "kind": "dns#change",
        "status": "done",
        "additions": added,
        "deletions": deleted,
        "startTime": now.isoformat(),
    }
