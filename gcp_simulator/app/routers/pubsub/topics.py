import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from gcp_simulator.app.db.engine import get_db
from gcp_simulator.app.models.pubsub import Message, PendingMessage, Subscription, Topic
from gcp_simulator.app.schemas.pubsub import PublishRequest, TopicCreate

router = APIRouter()


def _topic_name(project_id: str, name: str) -> str:
    return f"projects/{project_id}/topics/{name}"


def _topic_response(t: Topic) -> dict:
    return {
        "name": _topic_name(t.project_id, t.name),
        "labels": t.labels or {},
    }


@router.put("/v1/projects/{project_id}/topics/{topic_name}")
async def create_topic(
    project_id: str,
    topic_name: str,
    body: TopicCreate = TopicCreate(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Topic).where(Topic.project_id == project_id, Topic.name == topic_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _topic_response(existing)

    topic = Topic(
        id=uuid.uuid4(),
        project_id=project_id,
        name=topic_name,
        labels=body.labels,
        created_at=datetime.now(timezone.utc),
    )
    db.add(topic)
    await db.flush()
    return _topic_response(topic)


@router.get("/v1/projects/{project_id}/topics/{topic_name}")
async def get_topic(project_id: str, topic_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Topic).where(Topic.project_id == project_id, Topic.name == topic_name)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic {topic_name} not found")
    return _topic_response(topic)


@router.get("/v1/projects/{project_id}/topics")
async def list_topics(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Topic).where(Topic.project_id == project_id))
    topics = result.scalars().all()
    return {"topics": [_topic_response(t) for t in topics]}


@router.delete("/v1/projects/{project_id}/topics/{topic_name}", status_code=200)
async def delete_topic(project_id: str, topic_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Topic).where(Topic.project_id == project_id, Topic.name == topic_name)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic {topic_name} not found")
    await db.execute(delete(Topic).where(Topic.project_id == project_id, Topic.name == topic_name))
    return {}


@router.post("/v1/projects/{project_id}/topics/{topic_name}:publish")
async def publish_messages(
    project_id: str,
    topic_name: str,
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Topic).where(Topic.project_id == project_id, Topic.name == topic_name)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic {topic_name} not found")

    # Find subscriptions for this topic
    subs_result = await db.execute(
        select(Subscription).where(
            Subscription.topic_project_id == project_id,
            Subscription.topic_name == topic_name,
        )
    )
    subscriptions = subs_result.scalars().all()

    message_ids = []
    now = datetime.now(timezone.utc)

    for msg in body.messages:
        message_id = str(uuid.uuid4())
        message_ids.append(message_id)

        db_msg = Message(
            id=uuid.uuid4(),
            topic_project_id=project_id,
            topic_name=topic_name,
            message_id=message_id,
            data=msg.get("data"),
            attributes=msg.get("attributes", {}),
            publish_time=now,
        )
        db.add(db_msg)

        # Fan-out to all subscriptions
        for sub in subscriptions:
            pending = PendingMessage(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                message_id=message_id,
                ack_id=str(uuid.uuid4()),
                acked=False,
            )
            db.add(pending)

    await db.flush()
    return {"messageIds": message_ids}
