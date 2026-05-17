import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from gcp_simulator.app.db.engine import Base


class SpannerInstance(Base):
    __tablename__ = "instances"
    __table_args__ = (
        UniqueConstraint("project_id", "instance_id"),
        {"schema": "spanner"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[str] = mapped_column(Text, default="regional-us-central1")
    node_count: Mapped[int] = mapped_column(default=1)
    state: Mapped[str] = mapped_column(String(32), default="READY")
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SpannerDatabase(Base):
    __tablename__ = "databases"
    __table_args__ = (
        UniqueConstraint("project_id", "instance_id", "database_id"),
        {"schema": "spanner"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    database_id: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="READY")
    ddl_statements: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SpannerSession(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "spanner"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    database_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_use: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SpannerTransaction(Base):
    __tablename__ = "transactions"
    __table_args__ = {"schema": "spanner"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spanner.sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_id: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="READ_WRITE")
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
