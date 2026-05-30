import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.dms import DmsConnectionProfile

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/connectionProfiles"


def _profile_name(project_id: str, location: str, profile_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/connectionProfiles/{profile_id}"


def _profile_response(p: DmsConnectionProfile) -> dict:
    resp = {
        "name": _profile_name(p.project_id, p.location, p.profile_id),
        "displayName": p.display_name or p.profile_id,
        "state": p.state,
        "labels": p.labels or {},
        "createTime": p.created_at.isoformat() + "Z",
        "updateTime": p.updated_at.isoformat() + "Z",
    }
    # Embed the connection config under the db_type key (lowercase)
    db_type_key = p.db_type.lower()
    if p.connection_config:
        resp[db_type_key] = p.connection_config
    if p.error:
        resp["error"] = p.error
    return resp


async def _get_profile(
    db: AsyncSession, project_id: str, location: str, profile_id: str
) -> DmsConnectionProfile:
    result = await db.execute(
        select(DmsConnectionProfile).where(
            DmsConnectionProfile.project_id == project_id,
            DmsConnectionProfile.location == location,
            DmsConnectionProfile.profile_id == profile_id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"ConnectionProfile {profile_id} not found", "status": "NOT_FOUND"}},
        )
    return p


def _extract_db_type_and_config(body: dict) -> tuple[str, dict]:
    """Detect which DB type key is present in the request body and extract config."""
    known_types = {
        "mysql": "MYSQL",
        "postgresql": "POSTGRESQL",
        "alloydb": "ALLOYDB",
        "cloudsql": "CLOUDSQL",
        "oracle": "ORACLE",
        "sqlserver": "SQLSERVER",
    }
    for key, db_type in known_types.items():
        if key in body:
            return db_type, body[key]
    return body.get("dbType", "POSTGRESQL"), body.get("connectionConfig", {})


@router.post(_BASE)
async def create_connection_profile(
    project_id: str,
    location: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    profile_id = body.get("connectionProfileId") or body.get("profile_id", "")
    if not profile_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "connectionProfileId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(DmsConnectionProfile).where(
            DmsConnectionProfile.project_id == project_id,
            DmsConnectionProfile.location == location,
            DmsConnectionProfile.profile_id == profile_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"ConnectionProfile {profile_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    profile_body = body.get("connectionProfile", body)
    db_type, config = _extract_db_type_and_config(profile_body)
    now = datetime.now(timezone.utc)
    p = DmsConnectionProfile(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        profile_id=profile_id,
        display_name=profile_body.get("displayName"),
        db_type=db_type,
        connection_config=config,
        state="READY",
        labels=profile_body.get("labels", {}),
        created_at=now,
        updated_at=now,
    )
    db.add(p)
    await db.flush()
    return _profile_response(p)


@router.get(_BASE)
async def list_connection_profiles(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DmsConnectionProfile).where(
            DmsConnectionProfile.project_id == project_id,
            DmsConnectionProfile.location == location,
        )
    )
    profiles = result.scalars().all()
    return {"connectionProfiles": [_profile_response(p) for p in profiles]}


@router.get(_BASE + "/{profile_id}")
async def get_connection_profile(
    project_id: str,
    location: str,
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    return _profile_response(await _get_profile(db, project_id, location, profile_id))


@router.patch(_BASE + "/{profile_id}")
async def update_connection_profile(
    project_id: str,
    location: str,
    profile_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    p = await _get_profile(db, project_id, location, profile_id)
    if "displayName" in body:
        p.display_name = body["displayName"]
    if "labels" in body:
        p.labels = body["labels"]
    db_type, config = _extract_db_type_and_config(body)
    if config:
        p.connection_config = config
        p.db_type = db_type
    p.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _profile_response(p)


@router.delete(_BASE + "/{profile_id}", status_code=200)
async def delete_connection_profile(
    project_id: str,
    location: str,
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_profile(db, project_id, location, profile_id)
    await db.execute(
        delete(DmsConnectionProfile).where(
            DmsConnectionProfile.project_id == project_id,
            DmsConnectionProfile.location == location,
            DmsConnectionProfile.profile_id == profile_id,
        )
    )
    return {}
