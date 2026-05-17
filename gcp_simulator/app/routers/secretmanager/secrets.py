import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.secretmanager import Secret, SecretVersion

router = APIRouter()

_NOT_FOUND = lambda name: {
    "error": {"code": 404, "message": f"{name} not found", "status": "NOT_FOUND"}
}


def _secret_name(project_id: str, secret_id: str) -> str:
    return f"projects/{project_id}/secrets/{secret_id}"


def _version_name(project_id: str, secret_id: str, version_id: int) -> str:
    return f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"


def _secret_response(s: Secret) -> dict:
    return {
        "name": _secret_name(s.project_id, s.secret_id),
        "replication": s.replication,
        "labels": s.labels or {},
        "annotations": s.annotations or {},
        "createTime": s.created_at.isoformat(),
    }


def _version_response(project_id: str, secret_id: str, v: SecretVersion, include_payload: bool = False) -> dict:
    resp = {
        "name": _version_name(project_id, secret_id, v.version_id),
        "state": v.state,
        "createTime": v.create_time.isoformat(),
        "destroyTime": v.destroy_time.isoformat() if v.destroy_time else None,
    }
    if include_payload and v.payload_data is not None:
        resp["payload"] = {
            "data": base64.b64encode(v.payload_data).decode(),
            "dataCrc32c": v.payload_crc32c or "",
        }
    return resp


async def _get_secret(db: AsyncSession, project_id: str, secret_id: str) -> Secret:
    result = await db.execute(
        select(Secret).where(Secret.project_id == project_id, Secret.secret_id == secret_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail=_NOT_FOUND(_secret_name(project_id, secret_id)))
    return s


async def _resolve_version(db: AsyncSession, secret_db_id: uuid.UUID, version: str) -> SecretVersion:
    if version == "latest":
        result = await db.execute(
            select(SecretVersion)
            .where(SecretVersion.secret_id == secret_db_id, SecretVersion.state == "ENABLED")
            .order_by(SecretVersion.version_id.desc())
            .limit(1)
        )
    else:
        try:
            vid = int(version)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": {"code": 400, "message": "Invalid version", "status": "INVALID_ARGUMENT"}})
        result = await db.execute(
            select(SecretVersion).where(
                SecretVersion.secret_id == secret_db_id,
                SecretVersion.version_id == vid,
            )
        )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail={"error": {"code": 404, "message": "Version not found", "status": "NOT_FOUND"}})
    return v


# ── Secrets ───────────────────────────────────────────────────────────────────

@router.post("/v1/projects/{project_id}/secrets")
async def create_secret(
    project_id: str,
    secretId: str,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Secret).where(Secret.project_id == project_id, Secret.secret_id == secretId)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Secret {secretId} already exists")

    s = Secret(
        id=uuid.uuid4(),
        project_id=project_id,
        secret_id=secretId,
        replication={"automatic": {}},
        labels={},
        annotations={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(s)
    await db.flush()
    return _secret_response(s)


@router.get("/v1/projects/{project_id}/secrets")
async def list_secrets(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Secret).where(Secret.project_id == project_id))
    secrets = result.scalars().all()
    return {"secrets": [_secret_response(s) for s in secrets]}


@router.get("/v1/projects/{project_id}/secrets/{secret_id}")
async def get_secret(project_id: str, secret_id: str, db: AsyncSession = Depends(get_db)):
    s = await _get_secret(db, project_id, secret_id)
    return _secret_response(s)


@router.delete("/v1/projects/{project_id}/secrets/{secret_id}", status_code=200)
async def delete_secret(project_id: str, secret_id: str, db: AsyncSession = Depends(get_db)):
    s = await _get_secret(db, project_id, secret_id)
    await db.execute(delete(SecretVersion).where(SecretVersion.secret_id == s.id))
    await db.execute(
        delete(Secret).where(Secret.project_id == project_id, Secret.secret_id == secret_id)
    )
    return {}


# ── Versions ──────────────────────────────────────────────────────────────────

@router.post("/v1/projects/{project_id}/secrets/{secret_id}/versions:add")
async def add_secret_version(
    project_id: str,
    secret_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    s = await _get_secret(db, project_id, secret_id)

    payload = body.get("payload", {})
    raw_data = payload.get("data", "")
    crc32c = payload.get("dataCrc32c")

    try:
        decoded = base64.b64decode(raw_data)
    except Exception:
        decoded = raw_data.encode() if isinstance(raw_data, str) else raw_data

    # Auto-increment version_id
    max_result = await db.execute(
        select(func.max(SecretVersion.version_id)).where(SecretVersion.secret_id == s.id)
    )
    max_version = max_result.scalar() or 0
    next_version = max_version + 1

    v = SecretVersion(
        id=uuid.uuid4(),
        secret_id=s.id,
        version_id=next_version,
        state="ENABLED",
        payload_data=decoded,
        payload_crc32c=str(crc32c) if crc32c is not None else None,
        create_time=datetime.now(timezone.utc),
        destroy_time=None,
    )
    db.add(v)
    await db.flush()
    return _version_response(project_id, secret_id, v)


@router.get("/v1/projects/{project_id}/secrets/{secret_id}/versions")
async def list_versions(project_id: str, secret_id: str, db: AsyncSession = Depends(get_db)):
    s = await _get_secret(db, project_id, secret_id)
    result = await db.execute(
        select(SecretVersion).where(SecretVersion.secret_id == s.id)
    )
    versions = result.scalars().all()
    return {"versions": [_version_response(project_id, secret_id, v) for v in versions]}


@router.get("/v1/projects/{project_id}/secrets/{secret_id}/versions/{version}")
async def get_version(
    project_id: str, secret_id: str, version: str, db: AsyncSession = Depends(get_db)
):
    s = await _get_secret(db, project_id, secret_id)
    v = await _resolve_version(db, s.id, version)
    return _version_response(project_id, secret_id, v)


@router.post("/v1/projects/{project_id}/secrets/{secret_id}/versions/{version}:access")
async def access_version(
    project_id: str, secret_id: str, version: str, db: AsyncSession = Depends(get_db)
):
    s = await _get_secret(db, project_id, secret_id)
    v = await _resolve_version(db, s.id, version)
    if v.state != "ENABLED":
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": f"Version is {v.state}", "status": "FAILED_PRECONDITION"}},
        )
    return {
        "name": _version_name(project_id, secret_id, v.version_id),
        "payload": {
            "data": base64.b64encode(v.payload_data).decode() if v.payload_data else "",
            "dataCrc32c": v.payload_crc32c or "",
        },
    }


@router.post("/v1/projects/{project_id}/secrets/{secret_id}/versions/{version}:disable")
async def disable_version(
    project_id: str, secret_id: str, version: str, db: AsyncSession = Depends(get_db)
):
    s = await _get_secret(db, project_id, secret_id)
    v = await _resolve_version(db, s.id, version)
    v.state = "DISABLED"
    await db.flush()
    return _version_response(project_id, secret_id, v)


@router.post("/v1/projects/{project_id}/secrets/{secret_id}/versions/{version}:enable")
async def enable_version(
    project_id: str, secret_id: str, version: str, db: AsyncSession = Depends(get_db)
):
    s = await _get_secret(db, project_id, secret_id)
    v = await _resolve_version(db, s.id, version)
    v.state = "ENABLED"
    await db.flush()
    return _version_response(project_id, secret_id, v)


@router.post("/v1/projects/{project_id}/secrets/{secret_id}/versions/{version}:destroy")
async def destroy_version(
    project_id: str, secret_id: str, version: str, db: AsyncSession = Depends(get_db)
):
    s = await _get_secret(db, project_id, secret_id)
    v = await _resolve_version(db, s.id, version)
    v.state = "DESTROYED"
    v.payload_data = None
    v.destroy_time = datetime.now(timezone.utc)
    await db.flush()
    return _version_response(project_id, secret_id, v)
