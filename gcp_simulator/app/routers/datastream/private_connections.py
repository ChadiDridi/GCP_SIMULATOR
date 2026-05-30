import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.datastream import DatastreamPrivateConnection

router = APIRouter()

_BASE = "/v1/projects/{project_id}/locations/{location}/privateConnections"


def _conn_name(project_id: str, location: str, connection_id: str) -> str:
    return f"projects/{project_id}/locations/{location}/privateConnections/{connection_id}"


def _conn_response(c: DatastreamPrivateConnection) -> dict:
    resp = {
        "name": _conn_name(c.project_id, c.location, c.connection_id),
        "displayName": c.display_name or c.connection_id,
        "state": c.state,
        "vpcPeeringConfig": c.vpc_peering_config or {},
        "labels": c.labels or {},
        "createTime": c.created_at.isoformat() + "Z",
        "updateTime": c.updated_at.isoformat() + "Z",
    }
    if c.error:
        resp["error"] = c.error
    return resp


async def _get_conn(
    db: AsyncSession, project_id: str, location: str, connection_id: str
) -> DatastreamPrivateConnection:
    result = await db.execute(
        select(DatastreamPrivateConnection).where(
            DatastreamPrivateConnection.project_id == project_id,
            DatastreamPrivateConnection.location == location,
            DatastreamPrivateConnection.connection_id == connection_id,
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"PrivateConnection {connection_id} not found", "status": "NOT_FOUND"}},
        )
    return c


@router.post(_BASE)
async def create_private_connection(
    project_id: str,
    location: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    connection_id = body.get("privateConnectionId") or body.get("connection_id", "")
    if not connection_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "privateConnectionId is required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(DatastreamPrivateConnection).where(
            DatastreamPrivateConnection.project_id == project_id,
            DatastreamPrivateConnection.location == location,
            DatastreamPrivateConnection.connection_id == connection_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": 409, "message": f"PrivateConnection {connection_id} already exists", "status": "ALREADY_EXISTS"}},
        )

    conn_body = body.get("privateConnection", body)
    now = datetime.now(timezone.utc)
    c = DatastreamPrivateConnection(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        connection_id=connection_id,
        display_name=conn_body.get("displayName"),
        state="CREATED",
        vpc_peering_config=conn_body.get("vpcPeeringConfig", {}),
        labels=conn_body.get("labels", {}),
        created_at=now,
        updated_at=now,
    )
    db.add(c)
    await db.flush()
    return _conn_response(c)


@router.get(_BASE)
async def list_private_connections(
    project_id: str,
    location: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DatastreamPrivateConnection).where(
            DatastreamPrivateConnection.project_id == project_id,
            DatastreamPrivateConnection.location == location,
        )
    )
    conns = result.scalars().all()
    return {"privateConnections": [_conn_response(c) for c in conns]}


@router.get(_BASE + "/{connection_id}")
async def get_private_connection(
    project_id: str,
    location: str,
    connection_id: str,
    db: AsyncSession = Depends(get_db),
):
    return _conn_response(await _get_conn(db, project_id, location, connection_id))


@router.delete(_BASE + "/{connection_id}", status_code=200)
async def delete_private_connection(
    project_id: str,
    location: str,
    connection_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_conn(db, project_id, location, connection_id)
    await db.execute(
        delete(DatastreamPrivateConnection).where(
            DatastreamPrivateConnection.project_id == project_id,
            DatastreamPrivateConnection.location == location,
            DatastreamPrivateConnection.connection_id == connection_id,
        )
    )
    return {}
