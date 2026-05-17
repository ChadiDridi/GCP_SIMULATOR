import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ARRAY, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class Token(Base):
    __tablename__ = "tokens"
    __table_args__ = {"schema": "auth"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    service_account_email: Mapped[str | None] = mapped_column(String(512))
    scopes: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ServiceAccount(Base):
    __tablename__ = "service_accounts"
    __table_args__ = {"schema": "auth"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
