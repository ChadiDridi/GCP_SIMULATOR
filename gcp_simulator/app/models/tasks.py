import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class TaskQueue(Base):
    __tablename__ = "queues"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "name"),
        {"schema": "tasks"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="RUNNING")
    rate_limits: Mapped[dict] = mapped_column(JSON, default=dict)
    retry_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = {"schema": "tasks"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.queues.id", ondelete="CASCADE"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String(512), nullable=False)
    http_request: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_count: Mapped[int] = mapped_column(Integer, default=0)
    response_count: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(32), default="PENDING")
    last_attempt: Mapped[dict] = mapped_column(JSON, default=dict)
    first_attempt: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
