import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from gcp_simulator.app.db.engine import Base


class MemorystoreInstance(Base):
    __tablename__ = "instances"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "instance_id"),
        {"schema": "memorystore"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="BASIC")
    memory_size_gb: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(32), default="READY")
    host: Mapped[str] = mapped_column(String(128), default="127.0.0.1")
    port: Mapped[int] = mapped_column(Integer, default=6379)
    redis_version: Mapped[str] = mapped_column(String(32), default="REDIS_7_0")
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
