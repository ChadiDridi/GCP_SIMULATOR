import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from gcp_simulator.app.db.engine import Base


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("project_id", "location", "name"),
        {"schema": "dataform"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    git_remote_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("repository_id", "name"),
        {"schema": "dataform"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataform.repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    files: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CompilationResult(Base):
    __tablename__ = "compilation_results"
    __table_args__ = (
        UniqueConstraint("repository_id", "result_id"),
        {"schema": "dataform"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataform.repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    result_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    git_commitish: Mapped[str | None] = mapped_column(Text)
    code_compilation_config: Mapped[dict] = mapped_column(JSON, default=dict)
    compiled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compilation_errors: Mapped[list] = mapped_column(JSON, default=list)
