import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from gcp_simulator.app.db.engine import Base


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("project_id", "dataset_id"),
        {"schema": "bigquery"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    location: Mapped[str] = mapped_column(String(64), default="US")
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Table(Base):
    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint("project_id", "dataset_id", "table_id"),
        {"schema": "bigquery"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    table_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    schema_def: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pg_table_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"schema": "bigquery"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    job_id: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DONE")
    query: Mapped[str | None] = mapped_column(Text)
    result_rows: Mapped[dict | None] = mapped_column(JSONB)
    error_result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
