import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class CloudRunService(Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "service_name"),
        {"schema": "cloudrun"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image: Mapped[str] = mapped_column(Text, nullable=False)
    container_id: Mapped[str | None] = mapped_column(Text)
    host_port: Mapped[int | None] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    env_vars: Mapped[dict] = mapped_column(JSON, default=dict)
    container_port: Mapped[int] = mapped_column(Integer, default=8080)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CloudRunRevision(Base):
    __tablename__ = "revisions"
    __table_args__ = {"schema": "cloudrun"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image: Mapped[str] = mapped_column(Text, nullable=False)
    container_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
