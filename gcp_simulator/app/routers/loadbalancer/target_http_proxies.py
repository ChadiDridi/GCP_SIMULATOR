import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.loadbalancer import TargetHttpProxy

router = APIRouter()


def _proxy_response(p: TargetHttpProxy) -> dict:
    return {
        "kind": "compute#targetHttpProxy",
        "id": str(p.id),
        "name": p.name,
        "urlMap": p.url_map or "",
        "selfLink": (
            f"https://www.googleapis.com/compute/v1/projects/{p.project_id}"
            f"/global/targetHttpProxies/{p.name}"
        ),
        "creationTimestamp": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/compute/v1/projects/{project_id}/global/targetHttpProxies")
async def list_target_http_proxies(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TargetHttpProxy).where(TargetHttpProxy.project_id == project_id)
    )
    proxies = result.scalars().all()
    return {"kind": "compute#targetHttpProxyList", "items": [_proxy_response(p) for p in proxies]}


@router.post("/compute/v1/projects/{project_id}/global/targetHttpProxies", status_code=200)
async def create_target_http_proxy(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(TargetHttpProxy).where(
            TargetHttpProxy.project_id == project_id, TargetHttpProxy.name == name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"TargetHttpProxy {name} already exists")

    proxy = TargetHttpProxy(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        url_map=body.get("urlMap"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(proxy)
    await db.flush()
    return _proxy_response(proxy)


@router.get("/compute/v1/projects/{project_id}/global/targetHttpProxies/{name}")
async def get_target_http_proxy(project_id: str, name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TargetHttpProxy).where(
            TargetHttpProxy.project_id == project_id, TargetHttpProxy.name == name
        )
    )
    proxy = result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail=f"TargetHttpProxy {name} not found")
    return _proxy_response(proxy)


@router.patch("/compute/v1/projects/{project_id}/global/targetHttpProxies/{name}")
async def patch_target_http_proxy(
    project_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TargetHttpProxy).where(
            TargetHttpProxy.project_id == project_id, TargetHttpProxy.name == name
        )
    )
    proxy = result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail=f"TargetHttpProxy {name} not found")

    body = await request.json()
    if "urlMap" in body:
        proxy.url_map = body["urlMap"]
    await db.flush()
    return _proxy_response(proxy)


@router.delete(
    "/compute/v1/projects/{project_id}/global/targetHttpProxies/{name}",
    status_code=204,
)
async def delete_target_http_proxy(
    project_id: str,
    name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TargetHttpProxy).where(
            TargetHttpProxy.project_id == project_id, TargetHttpProxy.name == name
        )
    )
    proxy = result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail=f"TargetHttpProxy {name} not found")
    await db.execute(
        delete(TargetHttpProxy).where(
            TargetHttpProxy.project_id == project_id, TargetHttpProxy.name == name
        )
    )
