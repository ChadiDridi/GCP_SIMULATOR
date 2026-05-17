import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

ALL_SERVICES = [
    "gcs", "pubsub", "bigquery", "firestore",
    "cloudsql", "spanner", "bigtable", "memorystore",
    "cloudrun", "gce", "vpc", "lb",
    "secretmanager", "dataflow", "dataform",
    "iam", "dns", "scheduler", "tasks",
]

# Services that require Docker to function
DOCKER_REQUIRED = {"memorystore", "cloudrun", "cloudsql"}

# Services incompatible with SQLite mode
SQLITE_INCOMPATIBLE = {"bigquery", "spanner", "bigtable", "memorystore", "cloudsql", "cloudrun"}


@click.command("start")
@click.option("--services", "-s", default=None, help="Comma-separated service list, e.g. gcs,pubsub,bigquery")
@click.option("--all", "all_services", is_flag=True, default=False, help="Enable all services")
@click.option("--port", "-p", default=9099, show_default=True, help="Port to listen on")
@click.option("--data-dir", default="~/.gcp-sim", show_default=True, help="Data directory for DB and volumes")
@click.option("--project", default="local-dev", show_default=True, help="Default GCP project ID")
@click.option("--dev-token", default="dev-token", show_default=True, help="Always-valid Bearer token")
@click.option("--sqlite", is_flag=True, default=False, help="Use SQLite instead of PostgreSQL (limited)")
@click.option("--no-docker", is_flag=True, default=False, help="Skip Docker container management")
@click.option("--log-level", default="INFO", show_default=True, type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]))
@click.option("--pg-port", default=5432, show_default=True, help="PostgreSQL container port")
@click.option("--redis-port", default=6379, show_default=True, help="Redis container port")
def start_cmd(services, all_services, port, data_dir, project, dev_token, sqlite, no_docker, log_level, pg_port, redis_port):
    """Start the GCP simulator."""
    data_path = Path(data_dir).expanduser()
    data_path.mkdir(parents=True, exist_ok=True)

    # Resolve service list
    if all_services:
        enabled = list(ALL_SERVICES)
    elif services:
        enabled = [s.strip() for s in services.split(",") if s.strip() in ALL_SERVICES]
        unknown = [s.strip() for s in services.split(",") if s.strip() not in ALL_SERVICES]
        if unknown:
            console.print(f"[yellow]Warning: unknown services ignored: {unknown}[/yellow]")
    else:
        enabled = ["gcs", "pubsub", "bigquery", "firestore"]

    # SQLite mode filtering
    if sqlite:
        incompatible = [s for s in enabled if s in SQLITE_INCOMPATIBLE]
        if incompatible:
            console.print(f"[yellow]SQLite mode: disabling incompatible services: {incompatible}[/yellow]")
            enabled = [s for s in enabled if s not in SQLITE_INCOMPATIBLE]

    db_url = None

    if not sqlite and not no_docker:
        docker_services = [s for s in enabled if s in DOCKER_REQUIRED]
        needs_pg = any(s not in DOCKER_REQUIRED for s in enabled) or "cloudsql" not in enabled

        if needs_pg:
            console.print("[cyan]Starting PostgreSQL container...[/cyan]")
            try:
                from gcp_simulator.cli.docker_manager import ensure_postgres, docker_available
                if not docker_available():
                    console.print("[red]Docker not available. Use --no-docker with --sqlite or ensure Docker is running.[/red]")
                    sys.exit(1)
                db_url = ensure_postgres(data_path, pg_port)
                console.print(f"[green]PostgreSQL ready on port {pg_port}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to start PostgreSQL: {e}[/red]")
                sys.exit(1)

        if "memorystore" in enabled:
            console.print("[cyan]Starting Redis container...[/cyan]")
            try:
                from gcp_simulator.cli.docker_manager import ensure_redis
                ensure_redis(data_path, redis_port)
                console.print(f"[green]Redis ready on port {redis_port}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to start Redis: {e}[/red]")
                enabled.remove("memorystore")

    elif sqlite:
        db_url = f"sqlite+aiosqlite:///{data_path / 'gcp_sim.db'}"

    if db_url is None and not sqlite:
        db_url = f"postgresql+asyncpg://postgres:simulator-pg-pass@127.0.0.1:{pg_port}/gcp_simulator"

    # Write config
    config = {
        "port": port,
        "project_id": project,
        "dev_token": dev_token,
        "enabled_services": enabled,
        "db_url": db_url,
        "sqlite_mode": sqlite,
        "data_dir": str(data_path),
        "pg_port": pg_port,
        "redis_port": redis_port,
    }
    config_path = data_path / "config.json"
    config_path.write_text(json.dumps(config, indent=2))

    # Run Alembic migrations
    if not sqlite:
        console.print("[cyan]Running database migrations...[/cyan]")
        env = os.environ.copy()
        env["GCP_SIM_DATABASE_URL"] = db_url
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]Migration failed:\n{result.stderr}[/red]")
            sys.exit(1)
        console.print("[green]Migrations applied.[/green]")

    # Set env vars for the FastAPI app
    os.environ["GCP_SIM_DATABASE_URL"] = db_url or ""
    os.environ["GCP_SIM_PROJECT_ID"] = project
    os.environ["GCP_SIM_DEV_TOKEN"] = dev_token
    os.environ["GCP_SIM_LOG_LEVEL"] = log_level
    os.environ["GCP_SIM_ENABLED_SERVICES"] = ",".join(enabled)
    os.environ["GCP_SIM_SQLITE_MODE"] = "1" if sqlite else "0"
    os.environ["GCP_SIM_DATA_DIR"] = str(data_path)
    os.environ["GCP_SIM_REDIS_URL"] = f"redis://127.0.0.1:{redis_port}"

    _print_startup_table(enabled, port, project, dev_token)

    # Write PID file and start uvicorn
    pid_file = data_path / "gcp-sim.pid"
    pid_file.write_text(str(os.getpid()))

    import uvicorn
    uvicorn.run(
        "gcp_simulator.app.main:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level.lower(),
        reload=False,
    )


def _print_startup_table(enabled: list, port: int, project: str, dev_token: str):
    console.print("\n[bold green]GCP Simulator[/bold green] — local GCP services\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Service", style="white")
    table.add_column("Endpoint", style="dim")
    table.add_column("Status", justify="center")

    _endpoints = {
        "gcs": f"http://localhost:{port}/storage/v1/b",
        "pubsub": f"http://localhost:{port}/v1/projects/{project}/topics",
        "bigquery": f"http://localhost:{port}/bigquery/v2/projects/{project}/datasets",
        "firestore": f"http://localhost:{port}/v1/projects/{project}/databases/(default)/documents",
        "cloudsql": f"http://localhost:{port}/sql/v1beta4/projects/{project}/instances",
        "spanner": f"http://localhost:{port}/v1/projects/{project}/instances",
        "bigtable": f"http://localhost:{port}/v2/projects/{project}/instances",
        "memorystore": f"http://localhost:{port}/v1/projects/{project}/locations/us-central1/instances",
        "cloudrun": f"http://localhost:{port}/v1/projects/{project}/locations/us-central1/services",
        "gce": f"http://localhost:{port}/compute/v1/projects/{project}/zones/us-central1-a/instances",
        "vpc": f"http://localhost:{port}/compute/v1/projects/{project}/global/networks",
        "lb": f"http://localhost:{port}/compute/v1/projects/{project}/global/forwardingRules",
        "secretmanager": f"http://localhost:{port}/v1/projects/{project}/secrets",
        "dataflow": f"http://localhost:{port}/v1b3/projects/{project}/locations/us-central1/jobs",
        "dataform": f"http://localhost:{port}/v1beta1/projects/{project}/locations/us-central1/repositories",
        "iam": f"http://localhost:{port}/v1/projects/{project}/serviceAccounts",
        "dns": f"http://localhost:{port}/dns/v1/projects/{project}/managedZones",
        "scheduler": f"http://localhost:{port}/v1/projects/{project}/locations/us-central1/jobs",
        "tasks": f"http://localhost:{port}/v2/projects/{project}/locations/us-central1/queues",
    }

    for svc in enabled:
        table.add_row(svc, _endpoints.get(svc, ""), "[green]●[/green] running")

    console.print(table)
    console.print(f"\n[bold]Base URL:[/bold] http://localhost:{port}")
    console.print(f"[bold]Dev token:[/bold] Authorization: Bearer {dev_token}")
    console.print(f"[bold]API docs:[/bold] http://localhost:{port}/docs\n")
