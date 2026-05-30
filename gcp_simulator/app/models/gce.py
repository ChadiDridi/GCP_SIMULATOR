import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, BigInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class Instance(Base):
    __tablename__ = "instances"
    __table_args__ = (
        UniqueConstraint("project_id", "zone", "name"),
        {"schema": "gce"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    zone: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    machine_type: Mapped[str] = mapped_column(String(128), default="n1-standard-1")
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    network_interfaces: Mapped[list] = mapped_column(JSON, default=list)
    disks: Mapped[list] = mapped_column(JSON, default=list)
    instance_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    self_link: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Disk(Base):
    __tablename__ = "disks"
    __table_args__ = (
        UniqueConstraint("project_id", "zone", "name"),
        {"schema": "gce"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    zone: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    size_gb: Mapped[int | None] = mapped_column(BigInteger)
    disk_type: Mapped[str] = mapped_column(String(64), default="pd-standard")
    source_image: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="READY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
