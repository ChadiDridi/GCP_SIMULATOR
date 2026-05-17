import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.iam import RoleBinding

router = APIRouter()


def _binding_response(b: RoleBinding) -> dict:
    return {
        "role": b.role,
        "members": b.members or [],
    }


@router.post("/v1/projects/{project_id}:getIamPolicy")
async def get_iam_policy(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    resource = f"projects/{project_id}"
    result = await db.execute(
        select(RoleBinding).where(
            RoleBinding.project_id == project_id,
            RoleBinding.resource == resource,
        )
    )
    bindings = result.scalars().all()
    return {
        "version": 1,
        "etag": "ACAB",
        "bindings": [_binding_response(b) for b in bindings],
    }


@router.post("/v1/projects/{project_id}:setIamPolicy")
async def set_iam_policy(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    policy = body.get("policy", {})
    new_bindings = policy.get("bindings", [])
    resource = f"projects/{project_id}"
    now = datetime.now(timezone.utc)

    # Delete existing bindings for this resource
    await db.execute(
        delete(RoleBinding).where(
            RoleBinding.project_id == project_id,
            RoleBinding.resource == resource,
        )
    )

    saved = []
    for b in new_bindings:
        role = b.get("role")
        members = b.get("members", [])
        if not role:
            continue
        rb = RoleBinding(
            id=uuid.uuid4(),
            project_id=project_id,
            resource=resource,
            role=role,
            members=members,
            created_at=now,
        )
        db.add(rb)
        saved.append(rb)

    await db.flush()
    return {
        "version": 1,
        "etag": "ACAB",
        "bindings": [_binding_response(b) for b in saved],
    }


@router.post("/v1/projects/{project_id}:testIamPermissions")
async def test_iam_permissions(
    project_id: str,
    request: Request,
):
    """Always grant all requested permissions (simulator behaviour)."""
    body = await request.json()
    permissions = body.get("permissions", [])
    return {"permissions": permissions}
