"""Proxy requests to Cloud Run containers running locally."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.cloudrun import CloudRunService

router = APIRouter()


@router.api_route("/run/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def proxy_to_cloudrun(
    service_name: str,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Proxy requests to a locally running Cloud Run container."""
    result = await db.execute(
        select(CloudRunService).where(CloudRunService.service_name == service_name)
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail=f"Cloud Run service '{service_name}' not found")

    if not svc.host_port:
        raise HTTPException(status_code=503, detail=f"Service '{service_name}' has no running container")

    target_url = f"http://127.0.0.1:{svc.host_port}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=dict(upstream.headers),
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to service '{service_name}' on port {svc.host_port}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Service '{service_name}' timed out")


@router.api_route("/run/{service_name}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def proxy_to_cloudrun_root(
    service_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await proxy_to_cloudrun(service_name, "", request, db)
