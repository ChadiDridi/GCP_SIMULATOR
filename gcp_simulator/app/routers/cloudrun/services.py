import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.cloudrun import CloudRunRevision, CloudRunService
from gcp_simulator._internal.port_utils import find_free_port

router = APIRouter()


def _svc_response(svc: CloudRunService) -> dict:
    return {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {
            "name": svc.service_name,
            "namespace": svc.project_id,
            "labels": {"cloud.googleapis.com/location": svc.location},
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [{"image": svc.image}]
                }
            }
        },
        "status": {
            "url": svc.url or f"http://localhost/run/{svc.service_name}",
            "conditions": [{"type": "Ready", "status": "True" if svc.status == "RUNNING" else "False"}],
            "observedGeneration": 1,
        },
    }


@router.post("/v1/projects/{project_id}/locations/{location}/services")
async def create_service(
    project_id: str,
    location: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    service_name = body.get("metadata", {}).get("name") or body.get("name", "")
    if not service_name:
        raise HTTPException(status_code=400, detail="Service name required in metadata.name")

    spec = body.get("spec", {})
    template = spec.get("template", {})
    containers = template.get("spec", {}).get("containers", [{}])
    image = containers[0].get("image", "") if containers else ""
    env_list = containers[0].get("env", []) if containers else []
    env_vars = {e["name"]: e["value"] for e in env_list if "name" in e and "value" in e}
    container_port = containers[0].get("ports", [{}])[0].get("containerPort", 8080) if containers else 8080

    if not image:
        raise HTTPException(status_code=400, detail="Container image required")

    # Check duplicate
    existing = await db.execute(
        select(CloudRunService).where(
            CloudRunService.project_id == project_id,
            CloudRunService.location == location,
            CloudRunService.service_name == service_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Service {service_name} already exists")

    host_port = find_free_port()
    container_id = None
    status = "RUNNING"

    # Try real Docker execution
    try:
        from gcp_simulator.cli.docker_manager import pull_image_if_missing, run_container, docker_available
        if docker_available():
            await asyncio.to_thread(pull_image_if_missing, image)
            cid, host_port = await asyncio.to_thread(
                run_container, image, host_port,
                f"gcp-sim-cloudrun-{service_name}", env_vars, container_port
            )
            container_id = cid
        else:
            status = "RUNNING"  # dev mode: no real container
    except Exception as e:
        status = "FAILED"
        container_id = None

    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}/run/{service_name}"

    svc = CloudRunService(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        service_name=service_name,
        image=image,
        container_id=container_id,
        host_port=host_port,
        url=url,
        status=status,
        env_vars=env_vars,
        container_port=container_port,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(svc)

    # Record revision
    revision = CloudRunRevision(
        id=uuid.uuid4(),
        service_id=svc.id,
        revision_name=f"{service_name}-00001-abc",
        image=image,
        container_id=container_id,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
    )
    db.add(revision)
    await db.flush()
    return _svc_response(svc)


@router.get("/v1/projects/{project_id}/locations/{location}/services")
async def list_services(project_id: str, location: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CloudRunService).where(
            CloudRunService.project_id == project_id,
            CloudRunService.location == location,
        )
    )
    services = result.scalars().all()
    return {"apiVersion": "serving.knative.dev/v1", "kind": "ServiceList", "items": [_svc_response(s) for s in services]}


@router.get("/v1/projects/{project_id}/locations/{location}/services/{service_name}")
async def get_service(
    project_id: str, location: str, service_name: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CloudRunService).where(
            CloudRunService.project_id == project_id,
            CloudRunService.location == location,
            CloudRunService.service_name == service_name,
        )
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    return _svc_response(svc)


@router.delete("/v1/projects/{project_id}/locations/{location}/services/{service_name}")
async def delete_service(
    project_id: str, location: str, service_name: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CloudRunService).where(
            CloudRunService.project_id == project_id,
            CloudRunService.location == location,
            CloudRunService.service_name == service_name,
        )
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    if svc.container_id:
        try:
            from gcp_simulator.cli.docker_manager import stop_container
            await asyncio.to_thread(stop_container, svc.container_id)
        except Exception:
            pass

    await db.execute(
        delete(CloudRunService).where(
            CloudRunService.project_id == project_id,
            CloudRunService.location == location,
            CloudRunService.service_name == service_name,
        )
    )
    return {}
