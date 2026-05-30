import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class BigtableInstance(Base):
    __tablename__ = "instances"
    __table_args__ = (
        UniqueConstraint("project_id", "instance_id"),
        {"schema": "bigtable"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="PRODUCTION")
    state: Mapped[str] = mapped_column(String(32), default="READY")
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BigtableTable(Base):
    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint("project_id", "instance_id", "table_id"),
        {"schema": "bigtable"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    table_id: Mapped[str] = mapped_column(Text, nullable=False)
    column_families: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BigtableRow(Base):
    __tablename__ = "rows"
    __table_args__ = (
        UniqueConstraint("project_id", "instance_id", "table_id", "row_key"),
        {"schema": "bigtable"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    table_id: Mapped[str] = mapped_column(Text, nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    cells: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
