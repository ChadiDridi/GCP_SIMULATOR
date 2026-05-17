import click
from rich.console import Console

from gcp_simulator.cli.commands.start import start_cmd
from gcp_simulator.cli.commands.stop import stop_cmd
from gcp_simulator.cli.commands.status import status_cmd
from gcp_simulator.cli.commands.reset import reset_cmd
from gcp_simulator.cli.commands.service_account import service_account_group

console = Console()


@click.group()
@click.version_option(version="2.0.0", prog_name="gcp-sim")
def cli():
    """
    GCP Simulator — local GCP services for development.

    Like Azurite for Azure, but for GCP.

    \b
    Quick start:
      gcp-sim start --all                    # Start all services
      gcp-sim start -s gcs,pubsub,bigquery   # Start specific services
      gcp-sim status                         # Check what's running
      gcp-sim stop                           # Stop everything
      gcp-sim reset                          # Wipe all data
      gcp-sim service-account create         # Generate SA JSON key
    """


cli.add_command(start_cmd, name="start")
cli.add_command(stop_cmd, name="stop")
cli.add_command(status_cmd, name="status")
cli.add_command(reset_cmd, name="reset")
cli.add_command(service_account_group, name="service-account")


if __name__ == "__main__":
    cli()
