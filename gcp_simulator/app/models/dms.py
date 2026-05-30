import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class DmsConnectionProfile(Base):
    __tablename__ = "dms_connection_profiles"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "profile_id"),
        {"schema": "dms"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    # db_type: MYSQL, POSTGRESQL, ALLOYDB, CLOUDSQL, ORACLE, SQLSERVER
    db_type: Mapped[str] = mapped_column(String(32), default="POSTGRESQL")
    # connection_config stores type-specific fields (host, port, username, ssl, etc.)
    connection_config: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="READY")
    error: Mapped[dict | None] = mapped_column(JSON)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class DmsMigrationJob(Base):
    __tablename__ = "dms_migration_jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "job_id"),
        {"schema": "dms"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    # source and destination connection profile resource names
    source_profile: Mapped[str] = mapped_column(Text, nullable=False)
    destination_profile: Mapped[str] = mapped_column(Text, nullable=False)
    # migration_type: ONE_TIME, CONTINUOUS
    migration_type: Mapped[str] = mapped_column(String(32), default="ONE_TIME")
    # state: NOT_STARTED, FULL_DUMP, CDC, PROMOTE_IN_PROGRESS, COMPLETED, FAILED, STOPPED
    state: Mapped[str] = mapped_column(String(32), default="NOT_STARTED")
    # phase: FULL_DUMP, CDC, PROMOTE_IN_PROGRESS, WAITING_FOR_SOURCE_WRITES_TO_STOP
    phase: Mapped[str] = mapped_column(String(64), default="FULL_DUMP")
    error: Mapped[dict | None] = mapped_column(JSON)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    # vpc_peering_connectivity or reverse_ssh_connectivity config
    connectivity: Mapped[dict] = mapped_column(JSON, default=dict)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
