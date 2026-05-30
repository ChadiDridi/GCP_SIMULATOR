import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "pubsub"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "pubsub"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    push_endpoint: Mapped[str | None] = mapped_column(Text)
    ack_deadline_seconds: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": "pubsub"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    data: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PendingMessage(Base):
    __tablename__ = "pending_messages"
    __table_args__ = {"schema": "pubsub"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pubsub.subscriptions.id", ondelete="CASCADE"), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ack_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ack_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acked: Mapped[bool] = mapped_column(Boolean, default=False)
