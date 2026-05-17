import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.dataflow import DataflowJob

router = APIRouter()


def _job_response(job: DataflowJob) -> dict:
    return {
        "id": job.job_id,
        "projectId": job.project_id,
        "location": job.location,
        "name": job.name,
        "type": job.job_type,
        "currentState": job.state,
        "currentStateTime": (
            job.current_state_time.isoformat() if job.current_state_time else None
        ),
        "createTime": job.create_time.isoformat() if job.create_time else None,
        "startTime": job.start_time.isoformat() if job.start_time else None,
        "pipelineDescription": job.pipeline_description or {},
        "environment": job.environment or {},
    }


@router.post("/v1b3/projects/{project_id}/locations/{location}/jobs")
async def create_job(
    project_id: str,
    location: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    now = datetime.now(timezone.utc)
    job_id = str(uuid.uuid4())
    name = body.get("name", f"job-{job_id[:8]}")

    job = DataflowJob(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        job_id=job_id,
        name=name,
        job_type=body.get("type", "BATCH"),
        state="JOB_STATE_DONE",
        pipeline_description=body.get("pipelineDescription", {}),
        environment=body.get("environment", {}),
        current_state_time=now,
        create_time=now,
        start_time=now,
    )
    db.add(job)
    await db.flush()
    return _job_response(job)


@router.get("/v1b3/projects/{project_id}/locations/{location}/jobs")
async def list_jobs(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DataflowJob).where(
            DataflowJob.project_id == project_id,
            DataflowJob.location == location,
        )
    )
    jobs = result.scalars().all()
    return {"jobs": [_job_response(j) for j in jobs]}


@router.get("/v1b3/projects/{project_id}/locations/{location}/jobs/{job_id}")
async def get_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DataflowJob).where(
            DataflowJob.project_id == project_id,
            DataflowJob.location == location,
            DataflowJob.job_id == job_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _job_response(job)


@router.put("/v1b3/projects/{project_id}/locations/{location}/jobs/{job_id}")
async def update_job(
    project_id: str,
    location: str,
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DataflowJob).where(
            DataflowJob.project_id == project_id,
            DataflowJob.location == location,
            DataflowJob.job_id == job_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    body = await request.json()
    requested_state = body.get("requestedState")
    if requested_state:
        job.state = requested_state
        job.current_state_time = datetime.now(timezone.utc)
    await db.flush()
    return _job_response(job)


@router.get("/v1b3/projects/{project_id}/locations/{location}/jobs/{job_id}/metrics")
async def get_job_metrics(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DataflowJob).where(
            DataflowJob.project_id == project_id,
            DataflowJob.location == location,
            DataflowJob.job_id == job_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"metrics": []}
