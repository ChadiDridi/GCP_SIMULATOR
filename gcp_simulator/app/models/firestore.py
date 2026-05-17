import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from gcp_simulator.app.db.engine import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "database_id", "collection_id", "document_id"),
        {"schema": "firestore"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    database_id: Mapped[str] = mapped_column(String(255), nullable=False, default="(default)")
    collection_id: Mapped[str] = mapped_column(String(1500), nullable=False)
    document_id: Mapped[str] = mapped_column(String(1500), nullable=False)
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
