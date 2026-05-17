import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from gcp_simulator.app.db.engine import Base


class CloudSQLInstance(Base):
    __tablename__ = "instances"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "cloudsql"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    database_version: Mapped[str] = mapped_column(String(64), default="POSTGRES_15")
    connection_name: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(String(128), default="127.0.0.1")
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="RUNNABLE")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CloudSQLDatabase(Base):
    __tablename__ = "databases"
    __table_args__ = (
        UniqueConstraint("project_id", "instance_name", "name"),
        {"schema": "cloudsql"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_name: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    charset: Mapped[str] = mapped_column(String(32), default="utf8")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CloudSQLUser(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("project_id", "instance_name", "name"),
        {"schema": "cloudsql"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_name: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(String(128), default="%")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
