import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class Network(Base):
    __tablename__ = "networks"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "vpc"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    auto_create_subnetworks: Mapped[bool] = mapped_column(Boolean, default=True)
    routing_mode: Mapped[str] = mapped_column(String(32), default="REGIONAL")
    description: Mapped[str | None] = mapped_column(Text)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Subnetwork(Base):
    __tablename__ = "subnetworks"
    __table_args__ = (
        UniqueConstraint("project_id", "region", "name"),
        {"schema": "vpc"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    network_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_cidr_range: Mapped[str | None] = mapped_column(Text)
    private_ip_google_access: Mapped[bool] = mapped_column(Boolean, default=False)
    secondary_ranges: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class FirewallRule(Base):
    __tablename__ = "firewall_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "vpc"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    network_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1000)
    direction: Mapped[str] = mapped_column(String(16), default="INGRESS")
    action: Mapped[str] = mapped_column(String(16), default="ALLOW")
    match_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    target_tags: Mapped[list] = mapped_column(JSON, default=list)
    source_ranges: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
