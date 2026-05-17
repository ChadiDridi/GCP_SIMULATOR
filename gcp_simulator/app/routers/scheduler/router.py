import asyncio
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.scheduler import SchedulerJob

router = APIRouter()


def _job_response(job: SchedulerJob) -> dict:
    return {
        "name": (
            f"projects/{job.project_id}/locations/{job.location}/jobs/{job.name}"
        ),
        "description": job.description or "",
        "schedule": job.schedule or "",
        "timeZone": job.timezone,
        "state": job.state,
        "httpTarget": job.http_target or {},
        "pubsubTarget": job.pubsub_target or {},
        "lastAttemptTime": (
            job.last_attempt_time.isoformat() if job.last_attempt_time else None
        ),
        "nextScheduleTime": (
            job.next_schedule_time.isoformat() if job.next_schedule_time else None
        ),
        "status": job.status or {},
    }


@router.get("/v1/projects/{project_id}/locations/{location}/jobs")
async def list_jobs(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
        )
    )
    jobs = result.scalars().all()
    return {"jobs": [_job_response(j) for j in jobs]}


@router.post("/v1/projects/{project_id}/locations/{location}/jobs", status_code=200)
async def create_job(
    project_id: str,
    location: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    existing = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Job {name} already exists")

    job = SchedulerJob(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        name=name,
        description=body.get("description"),
        schedule=body.get("schedule"),
        timezone=body.get("timeZone", "UTC"),
        state="ENABLED",
        http_target=body.get("httpTarget", {}),
        pubsub_target=body.get("pubsubTarget", {}),
        status={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    return _job_response(job)


@router.get("/v1/projects/{project_id}/locations/{location}/jobs/{job_name}")
async def get_job(
    project_id: str,
    location: str,
    job_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == job_name,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
    return _job_response(job)


@router.patch("/v1/projects/{project_id}/locations/{location}/jobs/{job_name}")
async def patch_job(
    project_id: str,
    location: str,
    job_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == job_name,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_name} not found")

    body = await request.json()
    if "description" in body:
        job.description = body["description"]
    if "schedule" in body:
        job.schedule = body["schedule"]
    if "timeZone" in body:
        job.timezone = body["timeZone"]
    if "httpTarget" in body:
        job.http_target = body["httpTarget"]
    if "pubsubTarget" in body:
        job.pubsub_target = body["pubsubTarget"]
    await db.flush()
    return _job_response(job)


@router.delete("/v1/projects/{project_id}/locations/{location}/jobs/{job_name}", status_code=204)
async def delete_job(
    project_id: str,
    location: str,
    job_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == job_name,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
    await db.execute(
        delete(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == job_name,
        )
    )


@router.post("/v1/projects/{project_id}/locations/{location}/jobs/{job_name}:run")
async def run_job(
    project_id: str,
    location: str,
    job_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == job_name,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_name} not found")

    job.last_attempt_time = datetime.now(timezone.utc)
    await db.flush()

    http_target = job.http_target or {}
    pubsub_target = job.pubsub_target or {}

    if http_target.get("uri"):
        url = http_target["uri"]
        method = http_target.get("httpMethod", "POST")
        headers = http_target.get("headers", {})
        body_bytes = http_target.get("body", b"")

        async def _fire_http():
            async with httpx.AsyncClient() as client:
                await client.request(method, url, headers=headers, content=body_bytes)

        asyncio.create_task(_fire_http())

    return _job_response(job)


@router.post("/v1/projects/{project_id}/locations/{location}/jobs/{job_name}:pause")
async def pause_job(
    project_id: str,
    location: str,
    job_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == job_name,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
    job.state = "PAUSED"
    await db.flush()
    return _job_response(job)


@router.post("/v1/projects/{project_id}/locations/{location}/jobs/{job_name}:resume")
async def resume_job(
    project_id: str,
    location: str,
    job_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerJob).where(
            SchedulerJob.project_id == project_id,
            SchedulerJob.location == location,
            SchedulerJob.name == job_name,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
    job.state = "ENABLED"
    await db.flush()
    return _job_response(job)
