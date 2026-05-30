import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, BigInteger, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class AlloyDBCluster(Base):
    __tablename__ = "alloydb_clusters"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "cluster_id"),
        {"schema": "alloydb"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    network: Mapped[str | None] = mapped_column(Text)
    database_version: Mapped[str] = mapped_column(String(32), default="POSTGRES_15")
    cluster_type: Mapped[str] = mapped_column(String(32), default="PRIMARY")
    state: Mapped[str] = mapped_column(String(32), default="READY")
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    automated_backup_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AlloyDBInstance(Base):
    __tablename__ = "alloydb_instances"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "cluster_id", "instance_id"),
        {"schema": "alloydb"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    instance_type: Mapped[str] = mapped_column(String(32), default="PRIMARY")
    cpu_count: Mapped[int] = mapped_column(Integer, default=2)
    state: Mapped[str] = mapped_column(String(32), default="READY")
    ip_address: Mapped[str | None] = mapped_column(String(64))
    public_ip_address: Mapped[str | None] = mapped_column(String(64))
    database_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AlloyDBDatabase(Base):
    __tablename__ = "alloydb_databases"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "cluster_id", "database_name"),
        {"schema": "alloydb"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(255), nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    charset: Mapped[str] = mapped_column(String(32), default="UTF8")
    collation: Mapped[str] = mapped_column(String(64), default="en_US.UTF8")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AlloyDBUser(Base):
    __tablename__ = "alloydb_users"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "cluster_id", "user_name"),
        {"schema": "alloydb"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_type: Mapped[str] = mapped_column(String(32), default="BUILT_IN")
    database_roles: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AlloyDBBackup(Base):
    __tablename__ = "alloydb_backups"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "backup_id"),
        {"schema": "alloydb"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    backup_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    cluster_name: Mapped[str] = mapped_column(Text, nullable=False)
    database_version: Mapped[str] = mapped_column(String(32), default="POSTGRES_15")
    backup_type: Mapped[str] = mapped_column(String(32), default="ON_DEMAND")
    state: Mapped[str] = mapped_column(String(32), default="READY")
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    expire_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
