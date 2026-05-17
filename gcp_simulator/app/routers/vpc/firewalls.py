import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.vpc import FirewallRule

router = APIRouter()


def _firewall_response(fw: FirewallRule) -> dict:
    return {
        "kind": "compute#firewall",
        "id": str(fw.id),
        "name": fw.name,
        "network": fw.network_name,
        "priority": fw.priority,
        "direction": fw.direction,
        "action": fw.action,
        "matchRules": fw.match_rules or {},
        "targetTags": fw.target_tags or [],
        "sourceRanges": fw.source_ranges or [],
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{fw.project_id}/global/firewalls/{fw.name}"
        ),
        "creationTimestamp": fw.created_at.isoformat() if fw.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/global/firewalls")
async def list_firewalls(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FirewallRule).where(FirewallRule.project_id == project_id)
    )
    firewalls = result.scalars().all()
    return {
        "kind": "compute#firewallList",
        "items": [_firewall_response(fw) for fw in firewalls],
    }


@router.post("/compute/v1/projects/{project_id}/global/firewalls", status_code=200)
async def create_firewall(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(FirewallRule).where(
            FirewallRule.project_id == project_id,
            FirewallRule.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Firewall rule {name} already exists")

    fw = FirewallRule(
        id=uuid.uuid4(),
        project_id=project_id,
        network_name=body.get("network", ""),
        name=name,
        priority=body.get("priority", 1000),
        direction=body.get("direction", "INGRESS"),
        action=body.get("action", "ALLOW"),
        match_rules=body.get("matchRules", {}),
        target_tags=body.get("targetTags", []),
        source_ranges=body.get("sourceRanges", []),
        created_at=datetime.now(timezone.utc),
    )
    db.add(fw)
    await db.flush()
    return _firewall_response(fw)


@router.get("/compute/v1/projects/{project_id}/global/firewalls/{name}")
async def get_firewall(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FirewallRule).where(
            FirewallRule.project_id == project_id,
            FirewallRule.name == name,
        )
    )
    fw = result.scalar_one_or_none()
    if not fw:
        raise HTTPException(status_code=404, detail=f"Firewall rule {name} not found")
    return _firewall_response(fw)


@router.patch("/compute/v1/projects/{project_id}/global/firewalls/{name}")
async def patch_firewall(
    project_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FirewallRule).where(
            FirewallRule.project_id == project_id,
            FirewallRule.name == name,
        )
    )
    fw = result.scalar_one_or_none()
    if not fw:
        raise HTTPException(status_code=404, detail=f"Firewall rule {name} not found")

    body = await request.json()
    if "priority" in body:
        fw.priority = body["priority"]
    if "direction" in body:
        fw.direction = body["direction"]
    if "action" in body:
        fw.action = body["action"]
    if "matchRules" in body:
        fw.match_rules = body["matchRules"]
    if "targetTags" in body:
        fw.target_tags = body["targetTags"]
    if "sourceRanges" in body:
        fw.source_ranges = body["sourceRanges"]
    await db.flush()
    return _firewall_response(fw)


@router.delete("/compute/v1/projects/{project_id}/global/firewalls/{name}", status_code=204)
async def delete_firewall(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FirewallRule).where(
            FirewallRule.project_id == project_id,
            FirewallRule.name == name,
        )
    )
    fw = result.scalar_one_or_none()
    if not fw:
        raise HTTPException(status_code=404, detail=f"Firewall rule {name} not found")
    await db.execute(
        delete(FirewallRule).where(
            FirewallRule.project_id == project_id,
            FirewallRule.name == name,
        )
    )
