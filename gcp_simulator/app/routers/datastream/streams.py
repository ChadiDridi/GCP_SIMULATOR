import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.datastream import DatastreamStream

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/streams"


def _stream_name(project_id: str, location: str, stream_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/streams/{stream_id}"


def _stream_response(s: DatastreamStream) -> dict:
    return {
        "name": _stream_name(s.project_id, s.location, s.stream_id),
        "displayName": s.display_name or s.stream_id,
        "uid": str(s.id),
        "state": s.state,
        "sourceConfig": s.source_config or {},
        "destinationConfig": s.destination_config or {},
        "backfillAll": {} if s.backfill_strategy == "ALL" else None,
        "backfillNone": {} if s.backfill_strategy == "NONE" else None,
        "errors": s.errors or [],
        "labels": s.labels or {},
        "createTime": s.created_at.isoformat() + "Z",
        "updateTime": s.updated_at.isoformat() + "Z",
    }


async def _get_stream(
    db: AsyncSession, project_id: str, location: str, stream_id: str
) -> DatastreamStream:
    result = await db.execute(
        select(DatastreamStream).where(
            DatastreamStream.project_id == project_id,
            DatastreamStream.location == location,
            DatastreamStream.stream_id == stream_id,
        )
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Stream {stream_id} not found", "status": "NOT_FOUND"}},
        )
    return s


@router.post(_BASE)
async def create_stream(
    project_id: str,
    location: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    stream_id = body.get("streamId") or body.get("stream_id", "")
    if not stream_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "streamId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(DatastreamStream).where(
            DatastreamStream.project_id == project_id,
            DatastreamStream.location == location,
            DatastreamStream.stream_id == stream_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"Stream {stream_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    stream_body = body.get("stream", body)
    source_config = stream_body.get("sourceConfig", {})
    dest_config = stream_body.get("destinationConfig", {})
    if not source_config or not dest_config:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "sourceConfig and destinationConfig are required", "status": "INVALID_ARGUMENT"}},
        )

    backfill_strategy = "ALL" if "backfillAll" in stream_body else "NONE"
    now = datetime.now(timezone.utc)
    s = DatastreamStream(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        stream_id=stream_id,
        display_name=stream_body.get("displayName"),
        state="NOT_STARTED",
        source_config=source_config,
        destination_config=dest_config,
        backfill_strategy=backfill_strategy,
        errors=[],
        labels=stream_body.get("labels", {}),
        created_at=now,
        updated_at=now,
    )
    db.add(s)
    await db.flush()
    return _stream_response(s)


@router.get(_BASE)
async def list_streams(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DatastreamStream).where(
            DatastreamStream.project_id == project_id,
            DatastreamStream.location == location,
        )
    )
    streams = result.scalars().all()
    return {"streams": [_stream_response(s) for s in streams]}


@router.get(_BASE + "/{stream_id}")
async def get_stream(
    project_id: str,
    location: str,
    stream_id: str,
    db: AsyncSession = Depends(get_db),
):
    return _stream_response(await _get_stream(db, project_id, location, stream_id))


@router.patch(_BASE + "/{stream_id}")
async def update_stream(
    project_id: str,
    location: str,
    stream_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    s = await _get_stream(db, project_id, location, stream_id)
    if "displayName" in body:
        s.display_name = body["displayName"]
    if "labels" in body:
        s.labels = body["labels"]
    if "sourceConfig" in body:
        s.source_config = body["sourceConfig"]
    if "destinationConfig" in body:
        s.destination_config = body["destinationConfig"]
    if "backfillAll" in body:
        s.backfill_strategy = "ALL"
    elif "backfillNone" in body:
        s.backfill_strategy = "NONE"
    s.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _stream_response(s)


@router.post(_BASE + "/{stream_id}:start")
async def start_stream(
    project_id: str,
    location: str,
    stream_id: str,
    db: AsyncSession = Depends(get_db),
):
    s = await _get_stream(db, project_id, location, stream_id)
    if s.state not in ("NOT_STARTED", "PAUSED"):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Cannot start stream in state {s.state}", "status": "FAILED_PRECONDITION"}},
        )
    s.state = "RUNNING"
    s.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _stream_response(s)


@router.post(_BASE + "/{stream_id}:pause")
async def pause_stream(
    project_id: str,
    location: str,
    stream_id: str,
    db: AsyncSession = Depends(get_db),
):
    s = await _get_stream(db, project_id, location, stream_id)
    if s.state != "RUNNING":
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Cannot pause stream in state {s.state}", "status": "FAILED_PRECONDITION"}},
        )
    s.state = "PAUSED"
    s.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _stream_response(s)


@router.post(_BASE + "/{stream_id}:resume")
async def resume_stream(
    project_id: str,
    location: str,
    stream_id: str,
    db: AsyncSession = Depends(get_db),
):
    s = await _get_stream(db, project_id, location, stream_id)
    if s.state != "PAUSED":
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Cannot resume stream in state {s.state}", "status": "FAILED_PRECONDITION"}},
        )
    s.state = "RUNNING"
    s.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _stream_response(s)


@router.delete(_BASE + "/{stream_id}", status_code=200)
async def delete_stream(
    project_id: str,
    location: str,
    stream_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_stream(db, project_id, location, stream_id)
    await db.execute(
        delete(DatastreamStream).where(
            DatastreamStream.project_id == project_id,
            DatastreamStream.location == location,
            DatastreamStream.stream_id == stream_id,
        )
    )
    return {}
