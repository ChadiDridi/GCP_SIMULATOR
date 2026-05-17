import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.cloudsql import CloudSQLInstance, CloudSQLDatabase, CloudSQLUser
from gcp_simulator.app.config import settings as app_settings
from gcp_simulator._internal.port_utils import find_free_port

router = APIRouter()


def _instance_response(inst: CloudSQLInstance) -> dict:
    return {
        "kind": "sql#instance",
        "name": inst.name,
        "project": inst.project_id,
        "databaseVersion": inst.database_version,
        "connectionName": inst.connection_name,
        "state": inst.state,
        "settings": inst.settings or {},
        "ipAddresses": [{"ipAddress": inst.host, "type": "PRIMARY"}],
        "serverCaCert": None,
    }


def _db_response(d: CloudSQLDatabase) -> dict:
    return {
        "kind": "sql#database",
        "name": d.name,
        "instance": d.instance_name,
        "project": d.project_id,
        "charset": d.charset,
    }


def _user_response(u: CloudSQLUser) -> dict:
    return {
        "kind": "sql#user",
        "name": u.name,
        "host": u.host,
        "instance": u.instance_name,
        "project": u.project_id,
    }


# ── Instances ─────────────────────────────────────────────────────────────────

@router.post("/sql/v1beta4/projects/{project_id}/instances")
async def create_instance(project_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    name = body.get("name", "")
    if not name:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "name required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(CloudSQLInstance).where(
            CloudSQLInstance.project_id == project_id,
            CloudSQLInstance.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Instance {name} already exists")

    database_version = body.get("databaseVersion", "POSTGRES_15")
    port = find_free_port()
    connection_name = f"{project_id}:us-central1:{name}"
    container_id = None
    data_dir = Path(getattr(app_settings, "data_dir", "/tmp/gcp_simulator"))

    try:
        from gcp_simulator.cli.docker_manager import docker_available, run_cloudsql_postgres, run_cloudsql_mysql

        if await asyncio.to_thread(docker_available):
            if database_version.startswith("POSTGRES"):
                cid, port = await asyncio.to_thread(run_cloudsql_postgres, name, port, data_dir)
            elif database_version.startswith("MYSQL"):
                cid, port = await asyncio.to_thread(run_cloudsql_mysql, name, port, data_dir)
            else:
                cid = None
            container_id = cid
    except Exception:
        pass

    inst = CloudSQLInstance(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        database_version=database_version,
        connection_name=connection_name,
        host="127.0.0.1",
        port=port,
        container_id=container_id,
        state="RUNNABLE",
        settings=body.get("settings", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(inst)
    await db.flush()
    return _instance_response(inst)


@router.get("/sql/v1beta4/projects/{project_id}/instances")
async def list_instances(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CloudSQLInstance).where(CloudSQLInstance.project_id == project_id)
    )
    instances = result.scalars().all()
    return {"kind": "sql#instancesList", "items": [_instance_response(i) for i in instances]}


@router.get("/sql/v1beta4/projects/{project_id}/instances/{instance}")
async def get_instance(project_id: str, instance: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CloudSQLInstance).where(
            CloudSQLInstance.project_id == project_id,
            CloudSQLInstance.name == instance,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Instance {instance} not found", "status": "NOT_FOUND"}},
        )
    return _instance_response(inst)


@router.delete("/sql/v1beta4/projects/{project_id}/instances/{instance}", status_code=200)
async def delete_instance(project_id: str, instance: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CloudSQLInstance).where(
            CloudSQLInstance.project_id == project_id,
            CloudSQLInstance.name == instance,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Instance {instance} not found", "status": "NOT_FOUND"}},
        )

    if inst.container_id:
        try:
            from gcp_simulator.cli.docker_manager import stop_container
            await asyncio.to_thread(stop_container, inst.container_id, True)
        except Exception:
            pass

    await db.execute(
        delete(CloudSQLInstance).where(
            CloudSQLInstance.project_id == project_id,
            CloudSQLInstance.name == instance,
        )
    )
    return {}


# ── Databases ─────────────────────────────────────────────────────────────────

@router.post("/sql/v1beta4/projects/{project_id}/instances/{instance}/databases")
async def create_database(project_id: str, instance: str, body: dict, db: AsyncSession = Depends(get_db)):
    db_name = body.get("name", "")
    if not db_name:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "name required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(CloudSQLDatabase).where(
            CloudSQLDatabase.project_id == project_id,
            CloudSQLDatabase.instance_name == instance,
            CloudSQLDatabase.name == db_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Database {db_name} already exists")

    d = CloudSQLDatabase(
        id=uuid.uuid4(),
        instance_name=instance,
        project_id=project_id,
        name=db_name,
        charset=body.get("charset", "utf8"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(d)
    await db.flush()
    return _db_response(d)


@router.get("/sql/v1beta4/projects/{project_id}/instances/{instance}/databases")
async def list_databases(project_id: str, instance: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CloudSQLDatabase).where(
            CloudSQLDatabase.project_id == project_id,
            CloudSQLDatabase.instance_name == instance,
        )
    )
    databases = result.scalars().all()
    return {"kind": "sql#databasesList", "items": [_db_response(d) for d in databases]}


@router.delete(
    "/sql/v1beta4/projects/{project_id}/instances/{instance}/databases/{db_name}",
    status_code=200,
)
async def delete_database(
    project_id: str, instance: str, db_name: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CloudSQLDatabase).where(
            CloudSQLDatabase.project_id == project_id,
            CloudSQLDatabase.instance_name == instance,
            CloudSQLDatabase.name == db_name,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Database {db_name} not found", "status": "NOT_FOUND"}},
        )
    await db.execute(
        delete(CloudSQLDatabase).where(
            CloudSQLDatabase.project_id == project_id,
            CloudSQLDatabase.instance_name == instance,
            CloudSQLDatabase.name == db_name,
        )
    )
    return {}


# ── Users ─────────────────────────────────────────────────────────────────────

@router.post("/sql/v1beta4/projects/{project_id}/instances/{instance}/users")
async def create_user(project_id: str, instance: str, body: dict, db: AsyncSession = Depends(get_db)):
    user_name = body.get("name", "")
    if not user_name:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": 400, "message": "name required", "status": "INVALID_ARGUMENT"}},
        )

    existing = await db.execute(
        select(CloudSQLUser).where(
            CloudSQLUser.project_id == project_id,
            CloudSQLUser.instance_name == instance,
            CloudSQLUser.name == user_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"User {user_name} already exists")

    u = CloudSQLUser(
        id=uuid.uuid4(),
        instance_name=instance,
        project_id=project_id,
        name=user_name,
        host=body.get("host", "%"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(u)
    await db.flush()
    return _user_response(u)


@router.get("/sql/v1beta4/projects/{project_id}/instances/{instance}/users")
async def list_users(project_id: str, instance: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CloudSQLUser).where(
            CloudSQLUser.project_id == project_id,
            CloudSQLUser.instance_name == instance,
        )
    )
    users = result.scalars().all()
    return {"kind": "sql#usersList", "items": [_user_response(u) for u in users]}
