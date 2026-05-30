import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.alloydb import AlloyDBUser

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/clusters/{cluster_id}/users"


def _user_name(project_id: str, location: str, cluster_id: str, user_name: str) -> str:
    return f"projects/{project_id}/locations/{location}/clusters/{cluster_id}/users/{user_name}"


def _user_response(u: AlloyDBUser) -> dict:
    return {
        "name": _user_name(u.project_id, u.location, u.cluster_id, u.user_name),
        "userType": u.user_type,
        "databaseRoles": u.database_roles or [],
        "createTime": u.created_at.isoformat() + "Z",
    }


@router.post(_BASE)
async def create_user(
    project_id: str,
    location: str,
    cluster_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    user_id = body.get("userId") or body.get("user_name", "")
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "userId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(AlloyDBUser).where(
            AlloyDBUser.project_id == project_id,
            AlloyDBUser.location == location,
            AlloyDBUser.cluster_id == cluster_id,
            AlloyDBUser.user_name == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"User {user_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    user_body = body.get("user", body)
    u = AlloyDBUser(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        cluster_id=cluster_id,
        user_name=user_id,
        user_type=user_body.get("userType", "BUILT_IN"),
        database_roles=user_body.get("databaseRoles", []),
        created_at=datetime.now(timezone.utc),
    )
    db.add(u)
    await db.flush()
    return _user_response(u)


@router.get(_BASE)
async def list_users(
    project_id: str,
    location: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBUser).where(
            AlloyDBUser.project_id == project_id,
            AlloyDBUser.location == location,
            AlloyDBUser.cluster_id == cluster_id,
        )
    )
    users = result.scalars().all()
    return {"users": [_user_response(u) for u in users]}


@router.get(_BASE + "/{user_name}")
async def get_user(
    project_id: str,
    location: str,
    cluster_id: str,
    user_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBUser).where(
            AlloyDBUser.project_id == project_id,
            AlloyDBUser.location == location,
            AlloyDBUser.cluster_id == cluster_id,
            AlloyDBUser.user_name == user_name,
        )
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"User {user_name} not found", "status": "NOT_FOUND"}},
        )
    return _user_response(u)


@router.patch(_BASE + "/{user_name}")
async def update_user(
    project_id: str,
    location: str,
    cluster_id: str,
    user_name: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBUser).where(
            AlloyDBUser.project_id == project_id,
            AlloyDBUser.location == location,
            AlloyDBUser.cluster_id == cluster_id,
            AlloyDBUser.user_name == user_name,
        )
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"User {user_name} not found", "status": "NOT_FOUND"}},
        )
    if "databaseRoles" in body:
        u.database_roles = body["databaseRoles"]
    await db.flush()
    return _user_response(u)


@router.delete(_BASE + "/{user_name}", status_code=200)
async def delete_user(
    project_id: str,
    location: str,
    cluster_id: str,
    user_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlloyDBUser).where(
            AlloyDBUser.project_id == project_id,
            AlloyDBUser.location == location,
            AlloyDBUser.cluster_id == cluster_id,
            AlloyDBUser.user_name == user_name,
        )
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"User {user_name} not found", "status": "NOT_FOUND"}},
        )
    await db.execute(delete(AlloyDBUser).where(AlloyDBUser.id == u.id))
    return {}
