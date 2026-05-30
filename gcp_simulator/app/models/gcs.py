import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, BigInteger, Text, LargeBinary, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class Bucket(Base):
    __tablename__ = "buckets"
    __table_args__ = {"schema": "gcs"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(222), unique=True, nullable=False)
    location: Mapped[str] = mapped_column(String(64), default="US")
    storage_class: Mapped[str] = mapped_column(String(64), default="STANDARD")
    versioning: Mapped[bool] = mapped_column(Boolean, default=False)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Object(Base):
    __tablename__ = "objects"
    __table_args__ = (
        UniqueConstraint("bucket_name", "name"),
        {"schema": "gcs"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bucket_name: Mapped[str] = mapped_column(String(222), ForeignKey("gcs.buckets.name", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), default="application/octet-stream")
    size: Mapped[int | None] = mapped_column(BigInteger)
    md5_hash: Mapped[str | None] = mapped_column(String(64))
    crc32c: Mapped[str | None] = mapped_column(String(16))
    user_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    generation: Mapped[int] = mapped_column(BigInteger, default=1)
    data: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class ResumableUpload(Base):
    __tablename__ = "resumable_uploads"
    __table_args__ = {"schema": "gcs"}

    upload_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bucket_name: Mapped[str] = mapped_column(String(222), nullable=False)
    object_name: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), default="application/octet-stream")
    total_size: Mapped[int | None] = mapped_column(BigInteger)
    uploaded_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    chunks: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
