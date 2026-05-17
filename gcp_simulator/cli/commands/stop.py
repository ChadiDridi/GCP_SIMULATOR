import json
import os
import signal
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command("stop")
@click.option("--data-dir", default="~/.gcp-sim", show_default=True)
@click.option("--keep-containers", is_flag=True, default=False, help="Don't stop PostgreSQL/Redis containers")
def stop_cmd(data_dir, keep_containers):
    """Stop the GCP simulator."""
    data_path = Path(data_dir).expanduser()
    pid_file = data_path / "gcp-sim.pid"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            pid_file.unlink(missing_ok=True)
            console.print(f"[green]Stopped GCP simulator (PID {pid})[/green]")
        except ProcessLookupError:
            console.print("[yellow]Process not found (already stopped?)[/yellow]")
            pid_file.unlink(missing_ok=True)
        except Exception as e:
            console.print(f"[red]Error stopping process: {e}[/red]")
    else:
        console.print("[yellow]No PID file found — simulator may not be running[/yellow]")

    if not keep_containers:
        config_path = data_path / "config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text())
            enabled = config.get("enabled_services", [])
            try:
                from gcp_simulator.cli.docker_manager import stop_postgres, stop_redis
                stop_postgres()
                console.print("[dim]PostgreSQL container stopped[/dim]")
                if "memorystore" in enabled:
                    stop_redis()
                    console.print("[dim]Redis container stopped[/dim]")
            except Exception as e:
                console.print(f"[dim]Container cleanup: {e}[/dim]")
