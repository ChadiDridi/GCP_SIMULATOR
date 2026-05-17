import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from gcp_simulator.app.db.engine import Base


class DataflowJob(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "job_id"),
        {"schema": "dataflow"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), default="BATCH")
    state: Mapped[str] = mapped_column(String(64), default="JOB_STATE_DONE")
    pipeline_description: Mapped[dict] = mapped_column(JSONB, default=dict)
    environment: Mapped[dict] = mapped_column(JSONB, default=dict)
    current_state_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    create_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
