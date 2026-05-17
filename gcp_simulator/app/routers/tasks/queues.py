import asyncio
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.tasks import Task, TaskQueue

router = APIRouter()

_QUEUE_BASE = "/v2/projects/{project_id}/locations/{location}/queues"


def _queue_name(project_id: str, location: str, name: str) -> str:
    return f"projects/{project_id}/locations/{location}/queues/{name}"


def _queue_response(q: TaskQueue) -> dict:
    return {
        "name": _queue_name(q.project_id, q.location, q.name),
        "state": q.state,
        "rateLimits": q.rate_limits or {},
        "retryConfig": q.retry_config or {},
    }


def _task_response(t: Task, project_id: str, location: str, queue_name: str) -> dict:
    return {
        "name": f"projects/{project_id}/locations/{location}/queues/{queue_name}/tasks/{t.task_name}",
        "httpRequest": t.http_request or {},
        "scheduleTime": t.schedule_time.isoformat() + "Z" if t.schedule_time else None,
        "dispatchCount": t.dispatch_count,
        "responseCount": t.response_count,
        "state": t.state,
        "lastAttempt": t.last_attempt or {},
        "firstAttempt": t.first_attempt or {},
        "createTime": t.created_at.isoformat() + "Z",
    }


# ── Queues ─────────────────────────────────────────────────────────────────────

@router.post("/v2/projects/{project_id}/locations/{location}/queues")
async def create_queue(
    project_id: str,
    location: str,
    request_body: dict,
    db: AsyncSession = Depends(get_db),
):
    # Body has `name` as full resource name or just queue ID in `queue` field
    name_full = request_body.get("name", "")
    queue_id = name_full.split("/")[-1] if "/" in name_full else name_full
    if not queue_id:
        raise HTTPException(status_code=400, detail="Queue name required")

    existing = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Queue {queue_id} already exists")

    q = TaskQueue(
        id=uuid.uuid4(),
        project_id=project_id,
        location=location,
        name=queue_id,
        state="RUNNING",
        rate_limits=request_body.get("rateLimits", {}),
        retry_config=request_body.get("retryConfig", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.flush()
    return _queue_response(q)


@router.get("/v2/projects/{project_id}/locations/{location}/queues")
async def list_queues(project_id: str, location: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TaskQueue).where(TaskQueue.project_id == project_id, TaskQueue.location == location)
    )
    queues = result.scalars().all()
    return {"queues": [_queue_response(q) for q in queues]}


@router.get("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}")
async def get_queue(project_id: str, location: str, queue_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")
    return _queue_response(q)


@router.delete("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}")
async def delete_queue(project_id: str, location: str, queue_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")
    await db.execute(
        delete(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    return {}


@router.post("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}:pause")
async def pause_queue(project_id: str, location: str, queue_name: str, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(TaskQueue)
        .where(TaskQueue.project_id == project_id, TaskQueue.location == location, TaskQueue.name == queue_name)
        .values(state="PAUSED")
    )
    await db.flush()
    return {}


@router.post("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}:resume")
async def resume_queue(project_id: str, location: str, queue_name: str, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(TaskQueue)
        .where(TaskQueue.project_id == project_id, TaskQueue.location == location, TaskQueue.name == queue_name)
        .values(state="RUNNING")
    )
    await db.flush()
    return {}


@router.post("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}:purge")
async def purge_queue(project_id: str, location: str, queue_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")
    await db.execute(delete(Task).where(Task.queue_id == q.id))
    await db.flush()
    return _queue_response(q)


# ── Tasks ──────────────────────────────────────────────────────────────────────

@router.post("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}/tasks")
async def create_task(
    project_id: str,
    location: str,
    queue_name: str,
    background_tasks: BackgroundTasks,
    request_body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")

    task_body = request_body.get("task", request_body)
    task_name = task_body.get("name", "").split("/")[-1] or str(uuid.uuid4())
    http_req = task_body.get("httpRequest", {})
    schedule_time_str = task_body.get("scheduleTime")
    schedule_time = None
    if schedule_time_str:
        try:
            from datetime import datetime
            schedule_time = datetime.fromisoformat(schedule_time_str.replace("Z", "+00:00"))
        except Exception:
            pass

    task = Task(
        id=uuid.uuid4(),
        queue_id=q.id,
        task_name=task_name,
        http_request=http_req,
        schedule_time=schedule_time,
        state="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()

    # Dispatch immediately if no schedule_time or it's in the past
    if q.state == "RUNNING" and http_req.get("url"):
        background_tasks.add_task(_dispatch_task, task.id, http_req)

    return _task_response(task, project_id, location, queue_name)


@router.get("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}/tasks")
async def list_tasks(project_id: str, location: str, queue_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")
    tasks_result = await db.execute(select(Task).where(Task.queue_id == q.id))
    tasks = tasks_result.scalars().all()
    return {"tasks": [_task_response(t, project_id, location, queue_name) for t in tasks]}


@router.get("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}/tasks/{task_name}")
async def get_task(
    project_id: str, location: str, queue_name: str, task_name: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")
    task_result = await db.execute(
        select(Task).where(Task.queue_id == q.id, Task.task_name == task_name)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_name} not found")
    return _task_response(task, project_id, location, queue_name)


@router.delete("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}/tasks/{task_name}")
async def delete_task(
    project_id: str, location: str, queue_name: str, task_name: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")
    await db.execute(delete(Task).where(Task.queue_id == q.id, Task.task_name == task_name))
    return {}


@router.post("/v2/projects/{project_id}/locations/{location}/queues/{queue_name}/tasks/{task_name}:run")
async def run_task(
    project_id: str,
    location: str,
    queue_name: str,
    task_name: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TaskQueue).where(
            TaskQueue.project_id == project_id,
            TaskQueue.location == location,
            TaskQueue.name == queue_name,
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail=f"Queue {queue_name} not found")

    task_result = await db.execute(
        select(Task).where(Task.queue_id == q.id, Task.task_name == task_name)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_name} not found")

    if task.http_request.get("url"):
        background_tasks.add_task(_dispatch_task, task.id, task.http_request)

    return _task_response(task, project_id, location, queue_name)


async def _dispatch_task(task_id: uuid.UUID, http_request: dict):
    """Fire-and-forget HTTP task dispatch."""
    url = http_request.get("url")
    method = http_request.get("httpMethod", "POST")
    headers = http_request.get("headers", {})
    body = http_request.get("body")

    if not url:
        return

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.request(method=method, url=url, headers=headers, content=body)
    except Exception:
        pass
