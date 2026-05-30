import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, LargeBinary, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class Secret(Base):
    __tablename__ = "secrets"
    __table_args__ = (
        UniqueConstraint("project_id", "secret_id"),
        {"schema": "secretmanager"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_id: Mapped[str] = mapped_column(Text, nullable=False)
    replication: Mapped[dict] = mapped_column(JSON, default=lambda: {"automatic": {}})
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    annotations: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SecretVersion(Base):
    __tablename__ = "secret_versions"
    __table_args__ = {"schema": "secretmanager"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    secret_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("secretmanager.secrets.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="ENABLED")
    payload_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    payload_crc32c: Mapped[str | None] = mapped_column(String(64))
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    destroy_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
