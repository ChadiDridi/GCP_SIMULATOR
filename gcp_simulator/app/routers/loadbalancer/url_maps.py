import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.loadbalancer import UrlMap

router = APIRouter()


def _um_response(um: UrlMap) -> dict:
    return {
        "kind": "compute#urlMap",
        "id": str(um.id),
        "name": um.name,
        "defaultService": um.default_service or "",
        "hostRules": um.host_rules or [],
        "pathMatchers": um.path_matchers or [],
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{um.project_id}/global/urlMaps/{um.name}"
        ),
        "creationTimestamp": um.created_at.isoformat() if um.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/global/urlMaps")
async def list_url_maps(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UrlMap).where(UrlMap.project_id == project_id))
    maps = result.scalars().all()
    return {"kind": "compute#urlMapList", "items": [_um_response(m) for m in maps]}


@router.post("/compute/v1/projects/{project_id}/global/urlMaps", status_code=200)
async def create_url_map(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(UrlMap).where(UrlMap.project_id == project_id, UrlMap.name == name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"UrlMap {name} already exists")

    um = UrlMap(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        default_service=body.get("defaultService"),
        host_rules=body.get("hostRules", []),
        path_matchers=body.get("pathMatchers", []),
        created_at=datetime.now(timezone.utc),
    )
    db.add(um)
    await db.flush()
    return _um_response(um)


@router.get("/compute/v1/projects/{project_id}/global/urlMaps/{name}")
async def get_url_map(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UrlMap).where(UrlMap.project_id == project_id, UrlMap.name == name)
    )
    um = result.scalar_one_or_none()
    if not um:
        raise HTTPException(status_code=404, detail=f"UrlMap {name} not found")
    return _um_response(um)


@router.patch("/compute/v1/projects/{project_id}/global/urlMaps/{name}")
async def patch_url_map(
    project_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UrlMap).where(UrlMap.project_id == project_id, UrlMap.name == name)
    )
    um = result.scalar_one_or_none()
    if not um:
        raise HTTPException(status_code=404, detail=f"UrlMap {name} not found")

    body = await request.json()
    if "defaultService" in body:
        um.default_service = body["defaultService"]
    if "hostRules" in body:
        um.host_rules = body["hostRules"]
    if "pathMatchers" in body:
        um.path_matchers = body["pathMatchers"]
    await db.flush()
    return _um_response(um)


@router.delete("/compute/v1/projects/{project_id}/global/urlMaps/{name}", status_code=204)
async def delete_url_map(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UrlMap).where(UrlMap.project_id == project_id, UrlMap.name == name)
    )
    um = result.scalar_one_or_none()
    if not um:
        raise HTTPException(status_code=404, detail=f"UrlMap {name} not found")
    await db.execute(
        delete(UrlMap).where(UrlMap.project_id == project_id, UrlMap.name == name)
    )
