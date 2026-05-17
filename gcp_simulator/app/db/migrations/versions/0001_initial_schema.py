"""Initial schema — auth, gcs, pubsub, bigquery, firestore

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schemas
    for schema in ("auth", "gcs", "pubsub", "bigquery", "firestore", "bq_data"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # ── auth ──────────────────────────────────────────────────────────────────
    op.create_table(
        "service_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key_id", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(512), unique=True, nullable=False),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("public_key_pem", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="auth",
    )
    op.create_table(
        "tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.Text, unique=True, nullable=False),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("service_account_email", sa.String(512)),
        sa.Column("scopes", ARRAY(sa.Text)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="auth",
    )

    # ── gcs ───────────────────────────────────────────────────────────────────
    op.create_table(
        "buckets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(222), unique=True, nullable=False),
        sa.Column("location", sa.String(64), server_default="US"),
        sa.Column("storage_class", sa.String(64), server_default="STANDARD"),
        sa.Column("versioning", sa.Boolean, server_default="false"),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="gcs",
    )
    op.create_table(
        "objects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bucket_name", sa.String(222), sa.ForeignKey("gcs.buckets.name", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("content_type", sa.String(255), server_default="application/octet-stream"),
        sa.Column("size", sa.BigInteger),
        sa.Column("md5_hash", sa.String(64)),
        sa.Column("crc32c", sa.String(16)),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("generation", sa.BigInteger, server_default="1"),
        sa.Column("data", sa.LargeBinary),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("bucket_name", "name"),
        schema="gcs",
    )
    op.create_table(
        "resumable_uploads",
        sa.Column("upload_id", sa.String(64), primary_key=True),
        sa.Column("bucket_name", sa.String(222), nullable=False),
        sa.Column("object_name", sa.Text, nullable=False),
        sa.Column("content_type", sa.String(255), server_default="application/octet-stream"),
        sa.Column("total_size", sa.BigInteger),
        sa.Column("uploaded_bytes", sa.BigInteger, server_default="0"),
        sa.Column("chunks", sa.LargeBinary),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="gcs",
    )

    # ── pubsub ────────────────────────────────────────────────────────────────
    op.create_table(
        "topics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="pubsub",
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("topic_project_id", sa.String(255), nullable=False),
        sa.Column("topic_name", sa.String(255), nullable=False),
        sa.Column("push_endpoint", sa.Text),
        sa.Column("ack_deadline_seconds", sa.Integer, server_default="10"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="pubsub",
    )
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("topic_project_id", sa.String(255), nullable=False),
        sa.Column("topic_name", sa.String(255), nullable=False),
        sa.Column("message_id", sa.String(255), unique=True, nullable=False),
        sa.Column("data", sa.Text),
        sa.Column("attributes", JSONB, server_default="{}"),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=False),
        schema="pubsub",
    )
    op.create_table(
        "pending_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("pubsub.subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("ack_id", sa.String(512), unique=True, nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("ack_deadline", sa.DateTime(timezone=True)),
        sa.Column("acked", sa.Boolean, server_default="false"),
        schema="pubsub",
    )

    # ── bigquery ──────────────────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("dataset_id", sa.String(1024), nullable=False),
        sa.Column("location", sa.String(64), server_default="US"),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "dataset_id"),
        schema="bigquery",
    )
    op.create_table(
        "tables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("dataset_id", sa.String(1024), nullable=False),
        sa.Column("table_id", sa.String(1024), nullable=False),
        sa.Column("schema_def", JSONB, nullable=False),
        sa.Column("pg_table_name", sa.String(255), unique=True, nullable=False),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "dataset_id", "table_id"),
        schema="bigquery",
    )
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("job_id", sa.String(1024), unique=True, nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="DONE"),
        sa.Column("query", sa.Text),
        sa.Column("result_rows", JSONB),
        sa.Column("error_result", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="bigquery",
    )

    # ── firestore ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("database_id", sa.String(255), nullable=False),
        sa.Column("collection_id", sa.String(1500), nullable=False),
        sa.Column("document_id", sa.String(1500), nullable=False),
        sa.Column("fields", JSONB, nullable=False, server_default="{}"),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "database_id", "collection_id", "document_id"),
        schema="firestore",
    )


def downgrade() -> None:
    op.drop_table("documents", schema="firestore")
    op.drop_table("jobs", schema="bigquery")
    op.drop_table("tables", schema="bigquery")
    op.drop_table("datasets", schema="bigquery")
    op.drop_table("pending_messages", schema="pubsub")
    op.drop_table("messages", schema="pubsub")
    op.drop_table("subscriptions", schema="pubsub")
    op.drop_table("topics", schema="pubsub")
    op.drop_table("resumable_uploads", schema="gcs")
    op.drop_table("objects", schema="gcs")
    op.drop_table("buckets", schema="gcs")
    op.drop_table("tokens", schema="auth")
    op.drop_table("service_accounts", schema="auth")
    for schema in ("auth", "gcs", "pubsub", "bigquery", "firestore", "bq_data"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
