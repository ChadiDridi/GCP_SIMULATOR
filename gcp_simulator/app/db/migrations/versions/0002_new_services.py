"""New services: CloudSQL, Spanner, Bigtable, Memorystore, CloudRun, GCE, VPC, LB, SecretManager, Dataflow, Dataform, IAM, DNS, Scheduler, Tasks

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _schemas = [
        "cloudsql", "spanner", "bigtable", "memorystore", "cloudrun",
        "gce", "vpc", "loadbalancer", "secretmanager", "dataflow",
        "dataform", "iam", "dns", "scheduler", "tasks",
    ]
    for schema in _schemas:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # ── Cloud SQL ────────────────────────────────────────────────────────────
    op.create_table(
        "instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("database_version", sa.String(64), server_default="POSTGRES_15"),
        sa.Column("connection_name", sa.Text),
        sa.Column("host", sa.String(128), server_default="127.0.0.1"),
        sa.Column("port", sa.Integer),
        sa.Column("container_id", sa.Text),
        sa.Column("state", sa.String(32), server_default="RUNNABLE"),
        sa.Column("settings", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="cloudsql",
    )
    op.create_table(
        "databases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("instance_name", sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("charset", sa.String(32), server_default="utf8"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "instance_name", "name"),
        schema="cloudsql",
    )
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("instance_name", sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("host", sa.String(128), server_default="%"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "instance_name", "name"),
        schema="cloudsql",
    )

    # ── Spanner ──────────────────────────────────────────────────────────────
    op.create_table(
        "instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("instance_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(512)),
        sa.Column("config", sa.String(128), server_default="regional-us-central1"),
        sa.Column("node_count", sa.Integer, server_default="1"),
        sa.Column("state", sa.String(32), server_default="READY"),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "instance_id"),
        schema="spanner",
    )
    op.create_table(
        "databases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("instance_id", sa.String(255), nullable=False),
        sa.Column("database_id", sa.String(255), nullable=False),
        sa.Column("state", sa.String(32), server_default="READY"),
        sa.Column("ddl_statements", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "instance_id", "database_id"),
        schema="spanner",
    )
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("instance_id", sa.String(255), nullable=False),
        sa.Column("database_id", sa.String(255), nullable=False),
        sa.Column("session_id", sa.String(512), unique=True, nullable=False),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_use", sa.DateTime(timezone=True), nullable=False),
        schema="spanner",
    )
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("spanner.sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", sa.String(512), nullable=False),
        sa.Column("mode", sa.String(32), server_default="READ_WRITE"),
        sa.Column("committed_at", sa.DateTime(timezone=True)),
        sa.Column("rolled_back", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="spanner",
    )

    # ── Bigtable ─────────────────────────────────────────────────────────────
    op.create_table(
        "instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("instance_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(512)),
        sa.Column("type", sa.String(32), server_default="PRODUCTION"),
        sa.Column("state", sa.String(32), server_default="READY"),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "instance_id"),
        schema="bigtable",
    )
    op.create_table(
        "tables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("instance_id", sa.String(255), nullable=False),
        sa.Column("table_id", sa.String(255), nullable=False),
        sa.Column("column_families", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "instance_id", "table_id"),
        schema="bigtable",
    )
    op.create_table(
        "rows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("instance_id", sa.String(255), nullable=False),
        sa.Column("table_id", sa.String(255), nullable=False),
        sa.Column("row_key", sa.Text, nullable=False),
        sa.Column("cells", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "instance_id", "table_id", "row_key"),
        schema="bigtable",
    )

    # ── Memorystore ───────────────────────────────────────────────────────────
    op.create_table(
        "instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("instance_id", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(32), server_default="BASIC"),
        sa.Column("memory_size_gb", sa.Integer, server_default="1"),
        sa.Column("state", sa.String(32), server_default="READY"),
        sa.Column("host", sa.String(128), server_default="127.0.0.1"),
        sa.Column("port", sa.Integer, server_default="6379"),
        sa.Column("redis_version", sa.String(32), server_default="REDIS_7_0"),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "location", "instance_id"),
        schema="memorystore",
    )

    # ── Cloud Run ─────────────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("image", sa.Text, nullable=False),
        sa.Column("container_id", sa.Text),
        sa.Column("host_port", sa.Integer),
        sa.Column("url", sa.Text),
        sa.Column("status", sa.String(32), server_default="RUNNING"),
        sa.Column("env_vars", JSONB, server_default="{}"),
        sa.Column("container_port", sa.Integer, server_default="8080"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "location", "service_name"),
        schema="cloudrun",
    )
    op.create_table(
        "revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("cloudrun.services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_name", sa.String(255), nullable=False),
        sa.Column("image", sa.Text, nullable=False),
        sa.Column("container_id", sa.Text),
        sa.Column("status", sa.String(32), server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="cloudrun",
    )

    # ── GCE ──────────────────────────────────────────────────────────────────
    op.create_table(
        "instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("zone", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("machine_type", sa.String(128), server_default="n1-standard-1"),
        sa.Column("status", sa.String(32), server_default="RUNNING"),
        sa.Column("network_interfaces", JSONB, server_default="[]"),
        sa.Column("disks", JSONB, server_default="[]"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("tags", JSONB, server_default="{}"),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("self_link", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "zone", "name"),
        schema="gce",
    )
    op.create_table(
        "disks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("zone", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("size_gb", sa.BigInteger, server_default="10"),
        sa.Column("disk_type", sa.String(64), server_default="pd-standard"),
        sa.Column("source_image", sa.Text),
        sa.Column("status", sa.String(32), server_default="READY"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="gce",
    )

    # ── VPC ───────────────────────────────────────────────────────────────────
    op.create_table(
        "networks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("auto_create_subnetworks", sa.Boolean, server_default="true"),
        sa.Column("routing_mode", sa.String(32), server_default="REGIONAL"),
        sa.Column("description", sa.Text),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="vpc",
    )
    op.create_table(
        "subnetworks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("region", sa.String(128), nullable=False),
        sa.Column("network_name", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ip_cidr_range", sa.String(64)),
        sa.Column("private_ip_google_access", sa.Boolean, server_default="false"),
        sa.Column("secondary_ranges", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "region", "name"),
        schema="vpc",
    )
    op.create_table(
        "firewall_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("network_name", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("priority", sa.Integer, server_default="1000"),
        sa.Column("direction", sa.String(16), server_default="INGRESS"),
        sa.Column("action", sa.String(16), server_default="ALLOW"),
        sa.Column("match_rules", JSONB, server_default="{}"),
        sa.Column("target_tags", JSONB, server_default="[]"),
        sa.Column("source_ranges", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="vpc",
    )

    # ── Load Balancer ─────────────────────────────────────────────────────────
    op.create_table(
        "forwarding_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.Text),
        sa.Column("ip_protocol", sa.String(16), server_default="TCP"),
        sa.Column("port_range", sa.String(32)),
        sa.Column("target", sa.Text),
        sa.Column("load_balancing_scheme", sa.String(32), server_default="EXTERNAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="loadbalancer",
    )
    op.create_table(
        "backend_services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("protocol", sa.String(16), server_default="HTTP"),
        sa.Column("backends", JSONB, server_default="[]"),
        sa.Column("health_checks", JSONB, server_default="[]"),
        sa.Column("timeout_sec", sa.Integer, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="loadbalancer",
    )
    op.create_table(
        "health_checks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(16), server_default="HTTP"),
        sa.Column("port", sa.Integer, server_default="80"),
        sa.Column("request_path", sa.String(512), server_default="/"),
        sa.Column("check_interval_sec", sa.Integer, server_default="10"),
        sa.Column("timeout_sec", sa.Integer, server_default="5"),
        sa.Column("healthy_threshold", sa.Integer, server_default="2"),
        sa.Column("unhealthy_threshold", sa.Integer, server_default="2"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="loadbalancer",
    )
    op.create_table(
        "url_maps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_service", sa.Text),
        sa.Column("host_rules", JSONB, server_default="[]"),
        sa.Column("path_matchers", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="loadbalancer",
    )
    op.create_table(
        "target_http_proxies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url_map", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="loadbalancer",
    )

    # ── Secret Manager ────────────────────────────────────────────────────────
    op.create_table(
        "secrets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("secret_id", sa.String(255), nullable=False),
        sa.Column("replication", JSONB, server_default='{"automatic": {}}'),
        sa.Column("labels", JSONB, server_default="{}"),
        sa.Column("annotations", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "secret_id"),
        schema="secretmanager",
    )
    op.create_table(
        "secret_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("secret_id", UUID(as_uuid=True), sa.ForeignKey("secretmanager.secrets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Integer, nullable=False),
        sa.Column("state", sa.String(32), server_default="ENABLED"),
        sa.Column("payload_data", sa.LargeBinary),
        sa.Column("payload_crc32c", sa.Text),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("destroy_time", sa.DateTime(timezone=True)),
        schema="secretmanager",
    )

    # ── Dataflow ──────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("job_id", sa.String(512), unique=True, nullable=False),
        sa.Column("name", sa.String(512)),
        sa.Column("job_type", sa.String(32), server_default="BATCH"),
        sa.Column("state", sa.String(64), server_default="JOB_STATE_DONE"),
        sa.Column("pipeline_description", JSONB, server_default="{}"),
        sa.Column("environment", JSONB, server_default="{}"),
        sa.Column("current_state_time", sa.DateTime(timezone=True)),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True)),
        schema="dataflow",
    )

    # ── Dataform ──────────────────────────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("git_remote_settings", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "location", "name"),
        schema="dataform",
    )
    op.create_table(
        "workspaces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", UUID(as_uuid=True), sa.ForeignKey("dataform.repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("files", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="dataform",
    )
    op.create_table(
        "compilation_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", UUID(as_uuid=True), sa.ForeignKey("dataform.repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("result_id", sa.String(512), unique=True, nullable=False),
        sa.Column("git_commitish", sa.Text),
        sa.Column("code_compilation_config", JSONB, server_default="{}"),
        sa.Column("compiled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("compilation_errors", JSONB, server_default="[]"),
        schema="dataform",
    )

    # ── IAM ───────────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("role_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("included_permissions", JSONB, server_default="[]"),
        sa.Column("stage", sa.String(32), server_default="GA"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "role_id"),
        schema="iam",
    )
    op.create_table(
        "role_bindings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("resource", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("members", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="iam",
    )

    # ── Cloud DNS ─────────────────────────────────────────────────────────────
    op.create_table(
        "managed_zones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("dns_name", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("visibility", sa.String(16), server_default="public"),
        sa.Column("dnssec_config", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
        schema="dns",
    )
    op.create_table(
        "record_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", UUID(as_uuid=True), sa.ForeignKey("dns.managed_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("ttl", sa.Integer, server_default="300"),
        sa.Column("rrdatas", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="dns",
    )

    # ── Cloud Scheduler ───────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("schedule", sa.Text),
        sa.Column("timezone", sa.String(128), server_default="UTC"),
        sa.Column("state", sa.String(32), server_default="ENABLED"),
        sa.Column("target_type", sa.String(32)),
        sa.Column("http_target", JSONB, server_default="{}"),
        sa.Column("pubsub_target", JSONB, server_default="{}"),
        sa.Column("last_attempt_time", sa.DateTime(timezone=True)),
        sa.Column("next_schedule_time", sa.DateTime(timezone=True)),
        sa.Column("status", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "location", "name"),
        schema="scheduler",
    )

    # ── Cloud Tasks ───────────────────────────────────────────────────────────
    op.create_table(
        "queues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("state", sa.String(32), server_default="RUNNING"),
        sa.Column("rate_limits", JSONB, server_default="{}"),
        sa.Column("retry_config", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "location", "name"),
        schema="tasks",
    )
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_id", UUID(as_uuid=True), sa.ForeignKey("tasks.queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_name", sa.String(512), nullable=False),
        sa.Column("http_request", JSONB, server_default="{}"),
        sa.Column("schedule_time", sa.DateTime(timezone=True)),
        sa.Column("dispatch_count", sa.Integer, server_default="0"),
        sa.Column("response_count", sa.Integer, server_default="0"),
        sa.Column("state", sa.String(32), server_default="PENDING"),
        sa.Column("last_attempt", JSONB, server_default="{}"),
        sa.Column("first_attempt", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="tasks",
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("tasks", schema="tasks")
    op.drop_table("queues", schema="tasks")
    op.drop_table("jobs", schema="scheduler")
    op.drop_table("record_sets", schema="dns")
    op.drop_table("managed_zones", schema="dns")
    op.drop_table("role_bindings", schema="iam")
    op.drop_table("roles", schema="iam")
    op.drop_table("compilation_results", schema="dataform")
    op.drop_table("workspaces", schema="dataform")
    op.drop_table("repositories", schema="dataform")
    op.drop_table("jobs", schema="dataflow")
    op.drop_table("secret_versions", schema="secretmanager")
    op.drop_table("secrets", schema="secretmanager")
    op.drop_table("target_http_proxies", schema="loadbalancer")
    op.drop_table("url_maps", schema="loadbalancer")
    op.drop_table("health_checks", schema="loadbalancer")
    op.drop_table("backend_services", schema="loadbalancer")
    op.drop_table("forwarding_rules", schema="loadbalancer")
    op.drop_table("firewall_rules", schema="vpc")
    op.drop_table("subnetworks", schema="vpc")
    op.drop_table("networks", schema="vpc")
    op.drop_table("disks", schema="gce")
    op.drop_table("instances", schema="gce")
    op.drop_table("revisions", schema="cloudrun")
    op.drop_table("services", schema="cloudrun")
    op.drop_table("instances", schema="memorystore")
    op.drop_table("rows", schema="bigtable")
    op.drop_table("tables", schema="bigtable")
    op.drop_table("instances", schema="bigtable")
    op.drop_table("transactions", schema="spanner")
    op.drop_table("sessions", schema="spanner")
    op.drop_table("databases", schema="spanner")
    op.drop_table("instances", schema="spanner")
    op.drop_table("users", schema="cloudsql")
    op.drop_table("databases", schema="cloudsql")
    op.drop_table("instances", schema="cloudsql")
    for schema in ["cloudsql", "spanner", "bigtable", "memorystore", "cloudrun",
                   "gce", "vpc", "loadbalancer", "secretmanager", "dataflow",
                   "dataform", "iam", "dns", "scheduler", "tasks"]:
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
