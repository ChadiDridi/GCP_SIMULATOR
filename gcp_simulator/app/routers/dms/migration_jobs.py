import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.dms import DmsMigrationJob

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/migrationJobs"

_VALID_TRANSITIONS = {
    "NOT_STARTED": {"start"},
    "FULL_DUMP": {"stop"},
    "CDC": {"stop", "promote"},
    "STOPPED": {"resume", "delete"},
    "FAILED": {"restart", "delete"},
    "COMPLETED": set(),
}


def _job_name(project_id: str, location: str, job_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/migrationJobs/{job_id}"


def _job_response(j: DmsMigrationJob) -> dict:
    resp = {
        "name": _job_name(j.project_id, j.location, j.job_id),
        "displayName": j.display_name or j.job_id,
        "uid": str(j.id),
        "state": j.state,
        "phase": j.phase,
        "type": j.migration_type,
        "source": j.source_profile,
        "destination": j.destination_profile,
        "labels": j.labels or {},
        "createTime": j.created_at.isoformat() + "Z",
        "updateTime": j.updated_at.isoformat() + "Z",
    }
    if j.start_time:
        resp["startTime"] = j.start_time.isoformat() + "Z"
    if j.end_time:
        resp["endTime"] = j.end_time.isoformat() + "Z"
    if j.error:
        resp["error"] = j.error
    return resp


async def _get_job(
    db: AsyncSession, project_id: str, location: str, job_id: str
) -> DmsMigrationJob:
    result = await db.execute(
        select(DmsMigrationJob).where(
            DmsMigrationJob.project_id == project_id,
            DmsMigrationJob.location == location,
            DmsMigrationJob.job_id == job_id,
        )
    )
    j = result.scalar_one_or_none()
    if not j:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"MigrationJob {job_id} not found", "status": "NOT_FOUND"}},
        )
    return j


@router.post(_BASE)
async def create_migration_job(
    project_id: str,
    location: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    job_id = body.get("migrationJobId") or body.get("job_id", "")
    if not job_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "migrationJobId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(DmsMigrationJob).where(
            DmsMigrationJob.project_id == project_id,
            DmsMigrationJob.location == location,
            DmsMigrationJob.job_id == job_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"MigrationJob {job_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    job_body = body.get("migrationJob", body)
    source = job_body.get("source") or job_body.get("sourceConnectionProfile", "")
    destination = job_body.get("destination") or job_body.get("destinationConnectionProfile", "")
    if not source or not destination:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "source and destination connection profiles are required", "status": "INVALID_ARGUMENT"}},
        )

    now = datetime.now(timezone.utc)
    j = DmsMigrationJob(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        job_id=job_id,
        display_name=job_body.get("displayName"),
        source_profile=source,
        destination_profile=destination,
        migration_type=job_body.get("type", "ONE_TIME"),
        state="NOT_STARTED",
        phase="FULL_DUMP",
        labels=job_body.get("labels", {}),
        connectivity=job_body.get("vpcPeeringConnectivity") or job_body.get("reverseSshConnectivity") or {},
        created_at=now,
        updated_at=now,
    )
    db.add(j)
    await db.flush()
    return _job_response(j)


@router.get(_BASE)
async def list_migration_jobs(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DmsMigrationJob).where(
            DmsMigrationJob.project_id == project_id,
            DmsMigrationJob.location == location,
        )
    )
    jobs = result.scalars().all()
    return {"migrationJobs": [_job_response(j) for j in jobs]}


@router.get(_BASE + "/{job_id}")
async def get_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    return _job_response(await _get_job(db, project_id, location, job_id))


@router.patch(_BASE + "/{job_id}")
async def update_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    j = await _get_job(db, project_id, location, job_id)
    if "displayName" in body:
        j.display_name = body["displayName"]
    if "labels" in body:
        j.labels = body["labels"]
    j.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _job_response(j)


@router.post(_BASE + "/{job_id}:start")
async def start_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    j = await _get_job(db, project_id, location, job_id)
    if j.state not in ("NOT_STARTED", "STOPPED", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Cannot start job in state {j.state}", "status": "FAILED_PRECONDITION"}},
        )
    now = datetime.now(timezone.utc)
    j.state = "FULL_DUMP"
    j.phase = "FULL_DUMP"
    j.start_time = now
    j.updated_at = now
    await db.flush()
    return _job_response(j)


@router.post(_BASE + "/{job_id}:stop")
async def stop_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    j = await _get_job(db, project_id, location, job_id)
    if j.state not in ("FULL_DUMP", "CDC"):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Cannot stop job in state {j.state}", "status": "FAILED_PRECONDITION"}},
        )
    j.state = "STOPPED"
    j.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _job_response(j)


@router.post(_BASE + "/{job_id}:resume")
async def resume_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    j = await _get_job(db, project_id, location, job_id)
    if j.state != "STOPPED":
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Cannot resume job in state {j.state}", "status": "FAILED_PRECONDITION"}},
        )
    j.state = "CDC"
    j.phase = "CDC"
    j.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _job_response(j)


@router.post(_BASE + "/{job_id}:promote")
async def promote_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    j = await _get_job(db, project_id, location, job_id)
    if j.state != "CDC":
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Cannot promote job in state {j.state}", "status": "FAILED_PRECONDITION"}},
        )
    now = datetime.now(timezone.utc)
    j.state = "COMPLETED"
    j.phase = "PROMOTE_IN_PROGRESS"
    j.end_time = now
    j.updated_at = now
    await db.flush()
    return _job_response(j)


@router.post(_BASE + "/{job_id}:verify")
async def verify_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Runs connectivity checks against source and destination — always passes in the simulator."""
    j = await _get_job(db, project_id, location, job_id)
    return {
        "name": _job_name(j.project_id, j.location, j.job_id),
        "verificationResult": "OK",
        "warnings": [],
    }


@router.delete(_BASE + "/{job_id}", status_code=200)
async def delete_migration_job(
    project_id: str,
    location: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_job(db, project_id, location, job_id)
    await db.execute(
        delete(DmsMigrationJob).where(
            DmsMigrationJob.project_id == project_id,
            DmsMigrationJob.location == location,
            DmsMigrationJob.job_id == job_id,
        )
    )
    return {}
