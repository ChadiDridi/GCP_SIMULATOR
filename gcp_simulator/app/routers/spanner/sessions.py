import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.spanner import SpannerSession, SpannerTransaction

router = APIRouter()

_SESSION_BASE = (
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions"
)


def _session_name(project_id: str, instance_id: str, database_id: str, session_id: str) -> str:
    return f"projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}"


def _session_response(s: SpannerSession) -> dict:
    return {
        "name": _session_name(s.project_id, s.instance_id, s.database_id, s.session_id),
        "labels": s.labels or {},
        "createTime": s.created_at.isoformat(),
        "approximateLastUseTime": s.last_use.isoformat(),
    }


async def _get_session(db: AsyncSession, session_id: str) -> SpannerSession:
    result = await db.execute(
        select(SpannerSession).where(SpannerSession.session_id == session_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": 404, "message": f"Session {session_id} not found", "status": "NOT_FOUND"}},
        )
    return s


@router.post(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions"
)
async def create_session(
    project_id: str,
    instance_id: str,
    database_id: str,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or {}
    now = datetime.now(timezone.utc)
    session_id = str(uuid.uuid4())

    s = SpannerSession(
        id=uuid.uuid4(),
        project_id=project_id,
        instance_id=instance_id,
        database_id=database_id,
        session_id=session_id,
        labels=body.get("session", {}).get("labels", {}),
        created_at=now,
        last_use=now,
    )
    db.add(s)
    await db.flush()
    return _session_response(s)


@router.get(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}"
)
async def get_session(
    project_id: str,
    instance_id: str,
    database_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    s = await _get_session(db, session_id)
    return _session_response(s)


@router.delete(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}",
    status_code=200,
)
async def delete_session(
    project_id: str,
    instance_id: str,
    database_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_session(db, session_id)
    await db.execute(
        delete(SpannerSession).where(SpannerSession.session_id == session_id)
    )
    return {}


@router.post(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}:beginTransaction"
)
async def begin_transaction(
    project_id: str,
    instance_id: str,
    database_id: str,
    session_id: str,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or {}
    s = await _get_session(db, session_id)
    transaction_id = str(uuid.uuid4())
    mode = "READ_WRITE"
    options = body.get("options", {})
    if "readOnly" in options:
        mode = "READ_ONLY"
    elif "partitionedDml" in options:
        mode = "PARTITIONED_DML"

    txn = SpannerTransaction(
        id=uuid.uuid4(),
        session_id=s.id,
        transaction_id=transaction_id,
        mode=mode,
        created_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.flush()
    return {"id": transaction_id}


@router.post(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}:commit"
)
async def commit_transaction(
    project_id: str,
    instance_id: str,
    database_id: str,
    session_id: str,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or {}
    s = await _get_session(db, session_id)
    transaction_id = body.get("transactionId")
    if transaction_id:
        result = await db.execute(
            select(SpannerTransaction).where(
                SpannerTransaction.session_id == s.id,
                SpannerTransaction.transaction_id == transaction_id,
            )
        )
        txn = result.scalar_one_or_none()
        if txn:
            txn.committed_at = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    return {"commitTimestamp": now.isoformat()}


@router.post(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}:rollback"
)
async def rollback_transaction(
    project_id: str,
    instance_id: str,
    database_id: str,
    session_id: str,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or {}
    s = await _get_session(db, session_id)
    transaction_id = body.get("transactionId")
    if transaction_id:
        result = await db.execute(
            select(SpannerTransaction).where(
                SpannerTransaction.session_id == s.id,
                SpannerTransaction.transaction_id == transaction_id,
            )
        )
        txn = result.scalar_one_or_none()
        if txn:
            txn.rolled_back = True
    return {}


@router.post(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}:executeSql"
)
async def execute_sql(
    project_id: str,
    instance_id: str,
    database_id: str,
    session_id: str,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or {}
    await _get_session(db, session_id)
    sql = body.get("sql", "")
    if not sql:
        return {"rows": [], "metadata": {"rowType": {"fields": []}}}

    try:
        result = await db.execute(text(sql))
        try:
            rows = result.fetchall()
            keys = list(result.keys()) if rows else []
            return {
                "rows": [[str(v) for v in row] for row in rows],
                "metadata": {
                    "rowType": {
                        "fields": [{"name": k, "type": {"code": "STRING"}} for k in keys]
                    }
                },
            }
        except Exception:
            return {"rows": [], "metadata": {"rowType": {"fields": []}}}
    except Exception as e:
        return {"error": {"code": 400, "message": str(e), "status": "INVALID_ARGUMENT"}}


@router.post(
    "/v1/projects/{project_id}/instances/{instance_id}/databases/{database_id}/sessions/{session_id}:read"
)
async def read_data(
    project_id: str,
    instance_id: str,
    database_id: str,
    session_id: str,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
):
    await _get_session(db, session_id)
    return {"rows": []}
