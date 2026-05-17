import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.pubsub import Message, PendingMessage, Subscription, Topic
from gcp_simulator.app.schemas.pubsub import (
    AcknowledgeRequest,
    ModifyAckDeadlineRequest,
    PullRequest,
    SubscriptionCreate,
)

router = APIRouter()


def _sub_response(s: Subscription) -> dict:
    resp = {
        "name": f"projects/{s.project_id}/subscriptions/{s.name}",
        "topic": f"projects/{s.topic_project_id}/topics/{s.topic_name}",
        "ackDeadlineSeconds": s.ack_deadline_seconds,
        "pushConfig": {},
    }
    if s.push_endpoint:
        resp["pushConfig"] = {"pushEndpoint": s.push_endpoint}
    return resp


@router.put("/v1/projects/{project_id}/subscriptions/{sub_name}")
async def create_subscription(
    project_id: str,
    sub_name: str,
    body: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
):
    # Verify topic exists
    topic_resource = body.topic  # projects/{proj}/topics/{name}
    parts = topic_resource.split("/")
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail=f"Invalid topic name: {body.topic}")
    topic_project, topic_name = parts[1], parts[3]

    result = await db.execute(
        select(Topic).where(Topic.project_id == topic_project, Topic.name == topic_name)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Topic {topic_name} not found")

    existing = await db.execute(
        select(Subscription).where(Subscription.project_id == project_id, Subscription.name == sub_name)
    )
    if existing.scalar_one_or_none():
        return _sub_response(existing.scalar_one())

    push_endpoint = None
    if body.pushConfig:
        push_endpoint = body.pushConfig.get("pushEndpoint")

    sub = Subscription(
        id=uuid.uuid4(),
        project_id=project_id,
        name=sub_name,
        topic_project_id=topic_project,
        topic_name=topic_name,
        push_endpoint=push_endpoint,
        ack_deadline_seconds=body.ackDeadlineSeconds,
        created_at=datetime.now(timezone.utc),
    )
    db.add(sub)
    await db.flush()
    return _sub_response(sub)


@router.get("/v1/projects/{project_id}/subscriptions/{sub_name}")
async def get_subscription(project_id: str, sub_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription).where(Subscription.project_id == project_id, Subscription.name == sub_name)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Subscription {sub_name} not found")
    return _sub_response(sub)


@router.get("/v1/projects/{project_id}/subscriptions")
async def list_subscriptions(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Subscription).where(Subscription.project_id == project_id))
    subs = result.scalars().all()
    return {"subscriptions": [_sub_response(s) for s in subs]}


@router.delete("/v1/projects/{project_id}/subscriptions/{sub_name}", status_code=200)
async def delete_subscription(project_id: str, sub_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription).where(Subscription.project_id == project_id, Subscription.name == sub_name)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Subscription {sub_name} not found")
    await db.execute(
        delete(Subscription).where(Subscription.project_id == project_id, Subscription.name == sub_name)
    )
    return {}


@router.post("/v1/projects/{project_id}/subscriptions/{sub_name}:pull")
async def pull_messages(
    project_id: str,
    sub_name: str,
    body: PullRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription).where(Subscription.project_id == project_id, Subscription.name == sub_name)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Subscription {sub_name} not found")

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(seconds=sub.ack_deadline_seconds)

    # Get unacked pending messages (or those past deadline)
    pending_result = await db.execute(
        select(PendingMessage).where(
            PendingMessage.subscription_id == sub.id,
            PendingMessage.acked == False,  # noqa: E712
        ).limit(body.maxMessages)
    )
    pending = pending_result.scalars().all()

    received = []
    for pm in pending:
        # Fetch original message
        msg_result = await db.execute(
            select(Message).where(Message.message_id == pm.message_id)
        )
        msg = msg_result.scalar_one_or_none()
        if not msg:
            continue

        pm.delivered_at = now
        pm.ack_deadline = deadline

        received.append({
            "ackId": pm.ack_id,
            "message": {
                "data": msg.data or "",
                "attributes": msg.attributes or {},
                "messageId": msg.message_id,
                "publishTime": msg.publish_time.isoformat() + "Z",
            },
        })

    await db.flush()
    return {"receivedMessages": received}


@router.post("/v1/projects/{project_id}/subscriptions/{sub_name}:acknowledge")
async def acknowledge_messages(
    project_id: str,
    sub_name: str,
    body: AcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription).where(Subscription.project_id == project_id, Subscription.name == sub_name)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Subscription {sub_name} not found")

    await db.execute(
        update(PendingMessage)
        .where(PendingMessage.ack_id.in_(body.ackIds))
        .values(acked=True)
    )
    await db.flush()
    return {}


@router.post("/v1/projects/{project_id}/subscriptions/{sub_name}:modifyAckDeadline")
async def modify_ack_deadline(
    project_id: str,
    sub_name: str,
    body: ModifyAckDeadlineRequest,
    db: AsyncSession = Depends(get_db),
):
    new_deadline = datetime.now(timezone.utc) + timedelta(seconds=body.ackDeadlineSeconds)
    await db.execute(
        update(PendingMessage)
        .where(PendingMessage.ack_id.in_(body.ackIds))
        .values(ack_deadline=new_deadline)
    )
    await db.flush()
    return {}


async def _deliver_push(endpoint: str, payload: dict):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(endpoint, json=payload)
    except Exception:
        pass
