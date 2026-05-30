import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class DatastreamConnectionProfile(Base):
    __tablename__ = "ds_connection_profiles"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "profile_id"),
        {"schema": "datastream"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    # profile_type: ORACLE, MYSQL, POSTGRESQL, BIGQUERY, GCS
    profile_type: Mapped[str] = mapped_column(String(32), default="POSTGRESQL")
    # profile_config stores type-specific connection fields
    profile_config: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="CREATED")
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class DatastreamPrivateConnection(Base):
    __tablename__ = "ds_private_connections"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "connection_id"),
        {"schema": "datastream"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    connection_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(32), default="CREATED")
    # vpc_peering_config: {vpc, subnet}
    vpc_peering_config: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[dict | None] = mapped_column(JSON)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class DatastreamStream(Base):
    __tablename__ = "ds_streams"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "stream_id"),
        {"schema": "datastream"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    stream_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    # state: NOT_STARTED, RUNNING, PAUSED, MAINTENANCE, FAILED, FAILED_PERMANENTLY, STARTING
    state: Mapped[str] = mapped_column(String(32), default="NOT_STARTED")
    # source_config: {sourceConnectionProfile, mysqlSourceConfig/oracleSourceConfig/postgresqlSourceConfig}
    source_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # destination_config: {destinationConnectionProfile, gcsDestinationConfig/bigqueryDestinationConfig}
    destination_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # backfill_strategy: ALL or NONE
    backfill_strategy: Mapped[str] = mapped_column(String(16), default="NONE")
    errors: Mapped[list] = mapped_column(JSON, default=list)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
