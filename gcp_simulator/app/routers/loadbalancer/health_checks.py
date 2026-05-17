import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.loadbalancer import HealthCheck

router = APIRouter()


def _hc_response(hc: HealthCheck) -> dict:
    return {
        "kind": "compute#healthCheck",
        "id": str(hc.id),
        "name": hc.name,
        "type": hc.type,
        "port": hc.port,
        "requestPath": hc.request_path,
        "checkIntervalSec": hc.check_interval_sec,
        "timeoutSec": hc.timeout_sec,
        "healthyThreshold": hc.healthy_threshold,
        "unhealthyThreshold": hc.unhealthy_threshold,
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{hc.project_id}/global/healthChecks/{hc.name}"
        ),
        "creationTimestamp": hc.created_at.isoformat() if hc.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/global/healthChecks")
async def list_health_checks(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HealthCheck).where(HealthCheck.project_id == project_id)
    )
    checks = result.scalars().all()
    return {"kind": "compute#healthCheckList", "items": [_hc_response(c) for c in checks]}


@router.post("/compute/v1/projects/{project_id}/global/healthChecks", status_code=200)
async def create_health_check(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(HealthCheck).where(
            HealthCheck.project_id == project_id, HealthCheck.name == name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"HealthCheck {name} already exists")

    hc = HealthCheck(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        type=body.get("type", "HTTP"),
        port=body.get("port", 80),
        request_path=body.get("requestPath", "/"),
        check_interval_sec=body.get("checkIntervalSec", 10),
        timeout_sec=body.get("timeoutSec", 5),
        healthy_threshold=body.get("healthyThreshold", 2),
        unhealthy_threshold=body.get("unhealthyThreshold", 2),
        created_at=datetime.now(timezone.utc),
    )
    db.add(hc)
    await db.flush()
    return _hc_response(hc)


@router.get("/compute/v1/projects/{project_id}/global/healthChecks/{name}")
async def get_health_check(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.project_id == project_id, HealthCheck.name == name
        )
    )
    hc = result.scalar_one_or_none()
    if not hc:
        raise HTTPException(status_code=404, detail=f"HealthCheck {name} not found")
    return _hc_response(hc)


@router.patch("/compute/v1/projects/{project_id}/global/healthChecks/{name}")
async def patch_health_check(
    project_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.project_id == project_id, HealthCheck.name == name
        )
    )
    hc = result.scalar_one_or_none()
    if not hc:
        raise HTTPException(status_code=404, detail=f"HealthCheck {name} not found")

    body = await request.json()
    for field, attr in [
        ("type", "type"),
        ("port", "port"),
        ("requestPath", "request_path"),
        ("checkIntervalSec", "check_interval_sec"),
        ("timeoutSec", "timeout_sec"),
        ("healthyThreshold", "healthy_threshold"),
        ("unhealthyThreshold", "unhealthy_threshold"),
    ]:
        if field in body:
            setattr(hc, attr, body[field])
    await db.flush()
    return _hc_response(hc)


@router.delete("/compute/v1/projects/{project_id}/global/healthChecks/{name}", status_code=204)
async def delete_health_check(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.project_id == project_id, HealthCheck.name == name
        )
    )
    hc = result.scalar_one_or_none()
    if not hc:
        raise HTTPException(status_code=404, detail=f"HealthCheck {name} not found")
    await db.execute(
        delete(HealthCheck).where(
            HealthCheck.project_id == project_id, HealthCheck.name == name
        )
    )
