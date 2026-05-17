import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.loadbalancer import BackendService

router = APIRouter()


def _bs_response(bs: BackendService) -> dict:
    return {
        "kind": "compute#backendService",
        "id": str(bs.id),
        "name": bs.name,
        "protocol": bs.protocol,
        "backends": bs.backends or [],
        "healthChecks": bs.health_checks or [],
        "timeoutSec": bs.timeout_sec,
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{bs.project_id}/global/backendServices/{bs.name}"
        ),
        "creationTimestamp": bs.created_at.isoformat() if bs.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/global/backendServices")
async def list_backend_services(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BackendService).where(BackendService.project_id == project_id)
    )
    services = result.scalars().all()
    return {"kind": "compute#backendServiceList", "items": [_bs_response(s) for s in services]}


@router.post("/compute/v1/projects/{project_id}/global/backendServices", status_code=200)
async def create_backend_service(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(BackendService).where(
            BackendService.project_id == project_id, BackendService.name == name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"BackendService {name} already exists")

    bs = BackendService(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        protocol=body.get("protocol", "HTTP"),
        backends=body.get("backends", []),
        health_checks=body.get("healthChecks", []),
        timeout_sec=body.get("timeoutSec", 30),
        created_at=datetime.now(timezone.utc),
    )
    db.add(bs)
    await db.flush()
    return _bs_response(bs)


@router.get("/compute/v1/projects/{project_id}/global/backendServices/{name}")
async def get_backend_service(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BackendService).where(
            BackendService.project_id == project_id, BackendService.name == name
        )
    )
    bs = result.scalar_one_or_none()
    if not bs:
        raise HTTPException(status_code=404, detail=f"BackendService {name} not found")
    return _bs_response(bs)


@router.patch("/compute/v1/projects/{project_id}/global/backendServices/{name}")
async def patch_backend_service(
    project_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackendService).where(
            BackendService.project_id == project_id, BackendService.name == name
        )
    )
    bs = result.scalar_one_or_none()
    if not bs:
        raise HTTPException(status_code=404, detail=f"BackendService {name} not found")

    body = await request.json()
    if "protocol" in body:
        bs.protocol = body["protocol"]
    if "backends" in body:
        bs.backends = body["backends"]
    if "healthChecks" in body:
        bs.health_checks = body["healthChecks"]
    if "timeoutSec" in body:
        bs.timeout_sec = body["timeoutSec"]
    await db.flush()
    return _bs_response(bs)


@router.delete("/compute/v1/projects/{project_id}/global/backendServices/{name}", status_code=204)
async def delete_backend_service(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BackendService).where(
            BackendService.project_id == project_id, BackendService.name == name
        )
    )
    bs = result.scalar_one_or_none()
    if not bs:
        raise HTTPException(status_code=404, detail=f"BackendService {name} not found")
    await db.execute(
        delete(BackendService).where(
            BackendService.project_id == project_id, BackendService.name == name
        )
    )
