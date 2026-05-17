import asyncio
import json
from pathlib import Path

import click
from rich.console import Console

console = Console()

_SCHEMAS = [
    "auth", "gcs", "pubsub", "bigquery", "firestore", "bq_data",
    "cloudsql", "spanner", "bigtable", "memorystore", "cloudrun",
    "gce", "vpc", "loadbalancer", "secretmanager", "dataflow",
    "dataform", "iam", "dns", "scheduler", "tasks",
]

_SERVICE_TABLES = {
    "gcs": ["gcs.objects", "gcs.resumable_uploads", "gcs.buckets"],
    "pubsub": ["pubsub.pending_messages", "pubsub.messages", "pubsub.subscriptions", "pubsub.topics"],
    "bigquery": ["bigquery.jobs", "bigquery.tables", "bigquery.datasets"],
    "firestore": ["firestore.documents"],
    "auth": ["auth.tokens"],
    "secretmanager": ["secretmanager.secret_versions", "secretmanager.secrets"],
    "cloudrun": ["cloudrun.revisions", "cloudrun.services"],
    "gce": ["gce.disks", "gce.instances"],
    "vpc": ["vpc.firewall_rules", "vpc.subnetworks", "vpc.networks"],
    "lb": ["loadbalancer.target_http_proxies", "loadbalancer.url_maps", "loadbalancer.health_checks",
           "loadbalancer.backend_services", "loadbalancer.forwarding_rules"],
    "spanner": ["spanner.transactions", "spanner.sessions", "spanner.databases", "spanner.instances"],
    "bigtable": ["bigtable.rows", "bigtable.tables", "bigtable.instances"],
    "memorystore": ["memorystore.instances"],
    "cloudsql": ["cloudsql.users", "cloudsql.databases", "cloudsql.instances"],
    "dataflow": ["dataflow.jobs"],
    "dataform": ["dataform.compilation_results", "dataform.workspaces", "dataform.repositories"],
    "iam": ["iam.role_bindings", "iam.roles"],
    "dns": ["dns.record_sets", "dns.managed_zones"],
    "scheduler": ["scheduler.jobs"],
    "tasks": ["tasks.tasks", "tasks.queues"],
}


@click.command("reset")
@click.option("--service", "-s", default=None, help="Reset a specific service (leave empty for all)")
@click.option("--data-dir", default="~/.gcp-sim", show_default=True)
@click.confirmation_option(prompt="This will delete all simulator data. Continue?")
def reset_cmd(service, data_dir):
    """Reset simulator data (truncate tables)."""
    data_path = Path(data_dir).expanduser()
    config_path = data_path / "config.json"

    if not config_path.exists():
        console.print("[red]No config found — run 'gcp-sim start' first[/red]")
        return

    config = json.loads(config_path.read_text())
    db_url = config.get("db_url", "")

    asyncio.run(_do_reset(db_url, service))


async def _do_reset(db_url: str, service: str | None):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        if service:
            tables = _SERVICE_TABLES.get(service, [])
            if not tables:
                console.print(f"[red]Unknown service: {service}[/red]")
                return
            for table in tables:
                try:
                    await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                    console.print(f"[green]Truncated {table}[/green]")
                except Exception as e:
                    console.print(f"[yellow]Could not truncate {table}: {e}[/yellow]")
        else:
            # Truncate all in dependency order
            all_tables = []
            for tables in _SERVICE_TABLES.values():
                all_tables.extend(tables)
            for table in all_tables:
                try:
                    await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                except Exception:
                    pass
            # Drop and recreate bq_data schema
            try:
                await conn.execute(text("DROP SCHEMA IF EXISTS bq_data CASCADE"))
                await conn.execute(text("CREATE SCHEMA bq_data"))
            except Exception:
                pass
            console.print("[green]All data reset.[/green]")

    await engine.dispose()
