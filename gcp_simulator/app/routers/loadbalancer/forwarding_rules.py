import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.loadbalancer import ForwardingRule

router = APIRouter()


def _fr_response(fr: ForwardingRule) -> dict:
    return {
        "kind": "compute#forwardingRule",
        "id": str(fr.id),
        "name": fr.name,
        "IPAddress": fr.ip_address or "",
        "IPProtocol": fr.ip_protocol,
        "portRange": fr.port_range or "",
        "target": fr.target or "",
        "loadBalancingScheme": fr.load_balancing_scheme,
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{fr.project_id}/global/forwardingRules/{fr.name}"
        ),
        "creationTimestamp": fr.created_at.isoformat() if fr.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/global/forwardingRules")
async def list_forwarding_rules(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ForwardingRule).where(ForwardingRule.project_id == project_id)
    )
    rules = result.scalars().all()
    return {"kind": "compute#forwardingRuleList", "items": [_fr_response(r) for r in rules]}


@router.post("/compute/v1/projects/{project_id}/global/forwardingRules", status_code=200)
async def create_forwarding_rule(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(ForwardingRule).where(
            ForwardingRule.project_id == project_id, ForwardingRule.name == name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"ForwardingRule {name} already exists")

    fr = ForwardingRule(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        ip_address=body.get("IPAddress"),
        ip_protocol=body.get("IPProtocol", "TCP"),
        port_range=body.get("portRange"),
        target=body.get("target"),
        load_balancing_scheme=body.get("loadBalancingScheme", "EXTERNAL"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(fr)
    await db.flush()
    return _fr_response(fr)


@router.get("/compute/v1/projects/{project_id}/global/forwardingRules/{name}")
async def get_forwarding_rule(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ForwardingRule).where(
            ForwardingRule.project_id == project_id, ForwardingRule.name == name
        )
    )
    fr = result.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail=f"ForwardingRule {name} not found")
    return _fr_response(fr)


@router.patch("/compute/v1/projects/{project_id}/global/forwardingRules/{name}")
async def patch_forwarding_rule(
    project_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ForwardingRule).where(
            ForwardingRule.project_id == project_id, ForwardingRule.name == name
        )
    )
    fr = result.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail=f"ForwardingRule {name} not found")

    body = await request.json()
    for field, attr in [
        ("IPAddress", "ip_address"),
        ("IPProtocol", "ip_protocol"),
        ("portRange", "port_range"),
        ("target", "target"),
        ("loadBalancingScheme", "load_balancing_scheme"),
    ]:
        if field in body:
            setattr(fr, attr, body[field])
    await db.flush()
    return _fr_response(fr)


@router.delete("/compute/v1/projects/{project_id}/global/forwardingRules/{name}", status_code=204)
async def delete_forwarding_rule(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ForwardingRule).where(
            ForwardingRule.project_id == project_id, ForwardingRule.name == name
        )
    )
    fr = result.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail=f"ForwardingRule {name} not found")
    await db.execute(
        delete(ForwardingRule).where(
            ForwardingRule.project_id == project_id, ForwardingRule.name == name
        )
    )
