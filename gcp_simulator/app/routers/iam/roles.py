import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.iam import Role

router = APIRouter()


def _role_response(role: Role) -> dict:
    return {
        "name": f"projects/{role.project_id}/roles/{role.role_id}",
        "title": role.title or "",
        "description": role.description or "",
        "includedPermissions": role.included_permissions or [],
        "stage": role.stage,
        "etag": str(role.id),
    }


@router.get("/v1/projects/{project_id}/roles")
async def list_roles(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Role).where(Role.project_id == project_id))
    roles = result.scalars().all()
    return {"roles": [_role_response(r) for r in roles]}


@router.post("/v1/projects/{project_id}/roles", status_code=200)
async def create_role(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    role_id = body.get("roleId") or body.get("role", {}).get("roleId")
    if not role_id:
        raise HTTPException(status_code=400, detail="roleId is required")

    role_body = body.get("role", body)
    existing = await db.execute(
        select(Role).where(Role.project_id == project_id, Role.role_id == role_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Role {role_id} already exists")

    role = Role(
        id=uuid.uuid4(),
        project_id=project_id,
        role_id=role_id,
        title=role_body.get("title"),
        description=role_body.get("description"),
        included_permissions=role_body.get("includedPermissions", []),
        stage=role_body.get("stage", "GA"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(role)
    await db.flush()
    return _role_response(role)


@router.get("/v1/projects/{project_id}/roles/{role_id}")
async def get_role(project_id: str, role_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Role).where(Role.project_id == project_id, Role.role_id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
    return _role_response(role)


@router.patch("/v1/projects/{project_id}/roles/{role_id}")
async def patch_role(
    project_id: str,
    role_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Role).where(Role.project_id == project_id, Role.role_id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

    body = await request.json()
    if "title" in body:
        role.title = body["title"]
    if "description" in body:
        role.description = body["description"]
    if "includedPermissions" in body:
        role.included_permissions = body["includedPermissions"]
    if "stage" in body:
        role.stage = body["stage"]
    await db.flush()
    return _role_response(role)


@router.delete("/v1/projects/{project_id}/roles/{role_id}", status_code=204)
async def delete_role(project_id: str, role_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Role).where(Role.project_id == project_id, Role.role_id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
    await db.execute(
        delete(Role).where(Role.project_id == project_id, Role.role_id == role_id)
    )
