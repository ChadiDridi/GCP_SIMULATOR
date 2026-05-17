import json
import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command("status")
@click.option("--data-dir", default="~/.gcp-sim", show_default=True)
def status_cmd(data_dir):
    """Show status of GCP simulator and its services."""
    data_path = Path(data_dir).expanduser()
    pid_file = data_path / "gcp-sim.pid"
    config_path = data_path / "config.json"

    # Check process
    sim_running = False
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            sim_running = True
        except (ProcessLookupError, ValueError):
            pass

    status_icon = "[green]● running[/green]" if sim_running else "[red]● stopped[/red]"
    console.print(f"\nGCP Simulator: {status_icon}")

    if not config_path.exists():
        console.print("[dim]No config found — run 'gcp-sim start' first[/dim]")
        return

    config = json.loads(config_path.read_text())
    port = config.get("port", 9099)
    project = config.get("project_id", "local-dev")
    enabled = config.get("enabled_services", [])

    console.print(f"Port: {port}  |  Project: {project}\n")

    # Docker container statuses
    try:
        from gcp_simulator.cli.docker_manager import get_container_status
        pg_status = get_container_status("gcp-sim-postgres")
        redis_status = get_container_status("gcp-sim-redis")

        infra = Table(show_header=True, header_style="bold blue")
        infra.add_column("Infrastructure")
        infra.add_column("Status")
        infra.add_column("Port")

        pg_icon = "[green]●[/green]" if pg_status["status"] == "running" else "[red]●[/red]"
        redis_icon = "[green]●[/green]" if redis_status["status"] == "running" else "[dim]●[/dim]"
        infra.add_row("PostgreSQL", f"{pg_icon} {pg_status['status']}", str(config.get("pg_port", 5432)))
        infra.add_row("Redis", f"{redis_icon} {redis_status['status']}", str(config.get("redis_port", 6379)))
        console.print(infra)
    except Exception:
        pass

    # Services table
    svc_table = Table(show_header=True, header_style="bold cyan")
    svc_table.add_column("Service")
    svc_table.add_column("Status")
    svc_table.add_column("SDK Env Var / Connection")

    _sdk_hints = {
        "gcs": "client_options=ClientOptions(api_endpoint=...)",
        "bigquery": "BIGQUERY_EMULATOR_HOST=http://...",
        "pubsub": "transport='rest', client_options=...",
        "firestore": "client_options=ClientOptions(api_endpoint=...)",
        "secretmanager": "client_options=ClientOptions(api_endpoint=...)",
        "cloudsql": "Direct connect to 127.0.0.1:<port>",
        "memorystore": "redis.Redis(host='127.0.0.1', port=6379)",
        "cloudrun": "Proxied at /run/<service>/",
        "spanner": "client_options=ClientOptions(api_endpoint=...)",
    }

    for svc in enabled:
        icon = "[green]●[/green]" if sim_running else "[red]●[/red]"
        svc_table.add_row(svc, icon, _sdk_hints.get(svc, "REST API"))

    console.print(svc_table)
