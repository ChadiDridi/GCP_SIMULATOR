import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from gcp_simulator.app.db.engine import Base


class ForwardingRule(Base):
    __tablename__ = "forwarding_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "loadbalancer"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(Text)
    ip_protocol: Mapped[str] = mapped_column(String(16), default="TCP")
    port_range: Mapped[str | None] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    load_balancing_scheme: Mapped[str] = mapped_column(String(32), default="EXTERNAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BackendService(Base):
    __tablename__ = "backend_services"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "loadbalancer"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), default="HTTP")
    backends: Mapped[list] = mapped_column(JSONB, default=list)
    health_checks: Mapped[list] = mapped_column(JSONB, default=list)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class HealthCheck(Base):
    __tablename__ = "health_checks"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "loadbalancer"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(16), default="HTTP")
    port: Mapped[int] = mapped_column(Integer, default=80)
    request_path: Mapped[str] = mapped_column(Text, default="/")
    check_interval_sec: Mapped[int] = mapped_column(Integer, default=10)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=5)
    healthy_threshold: Mapped[int] = mapped_column(Integer, default=2)
    unhealthy_threshold: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class UrlMap(Base):
    __tablename__ = "url_maps"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "loadbalancer"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_service: Mapped[str | None] = mapped_column(Text)
    host_rules: Mapped[list] = mapped_column(JSONB, default=list)
    path_matchers: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class TargetHttpProxy(Base):
    __tablename__ = "target_http_proxies"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "loadbalancer"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url_map: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
