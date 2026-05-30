import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class SchedulerJob(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "name"),
        {"schema": "scheduler"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schedule: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    state: Mapped[str] = mapped_column(String(32), default="ENABLED")
    target_type: Mapped[str | None] = mapped_column(Text)
    http_target: Mapped[dict] = mapped_column(JSON, default=dict)
    pubsub_target: Mapped[dict] = mapped_column(JSON, default=dict)
    last_attempt_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_schedule_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
