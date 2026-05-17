import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group("service-account")
def service_account_group():
    """Manage simulator service accounts."""


@service_account_group.command("create")
@click.option("--project", default="local-dev", show_default=True)
@click.option("--email", default=None, help="Service account email (auto-generated if omitted)")
@click.option("--output", "-o", default="service-account.json", show_default=True, help="Output JSON key file path")
@click.option("--data-dir", default="~/.gcp-sim", show_default=True)
@click.option("--token-uri", default=None, help="Token URI (auto-derived from config if omitted)")
def create_cmd(project, email, output, data_dir, token_uri):
    """Generate a service account JSON key for SDK authentication."""
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        console.print("[red]cryptography package required: pip install cryptography[/red]")
        raise SystemExit(1)

    data_path = Path(data_dir).expanduser()
    config_path = data_path / "config.json"

    port = 9099
    if config_path.exists():
        config = json.loads(config_path.read_text())
        port = config.get("port", 9099)
        project = project or config.get("project_id", "local-dev")

    if not token_uri:
        token_uri = f"http://localhost:{port}/o/oauth2/token"

    if not email:
        email = f"simulator@{project}.iam.gserviceaccount.com"

    key_id = str(uuid.uuid4()).replace("-", "")[:24]
    client_id = str(int(uuid.uuid4().int % (10 ** 21))).zfill(21)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    key_data = {
        "type": "service_account",
        "project_id": project,
        "private_key_id": key_id,
        "private_key": private_pem,
        "client_email": email,
        "client_id": client_id,
        "auth_uri": token_uri.replace("/o/oauth2/token", "/o/oauth2/auth"),
        "token_uri": token_uri,
        "auth_provider_x509_cert_url": token_uri.replace("/o/oauth2/token", "/oauth2/v1/certs"),
        "client_x509_cert_url": token_uri.replace("/o/oauth2/token", "/oauth2/v1/certs"),
    }

    Path(output).write_text(json.dumps(key_data, indent=2))
    console.print(f"[green]Service account key written to: {output}[/green]")

    # Register in DB if reachable
    _register_in_db(data_path, key_id, email, project, public_pem)

    console.print(f"\n[bold]To use:[/bold]")
    console.print(f"  export GOOGLE_APPLICATION_CREDENTIALS={Path(output).resolve()}")
    console.print(f"  [dim]token_uri in key file: {token_uri}[/dim]")


def _register_in_db(data_path: Path, key_id: str, email: str, project_id: str, public_pem: str):
    config_path = data_path / "config.json"
    if not config_path.exists():
        console.print("[yellow]Simulator not running — key not registered in DB. Start simulator and re-run.[/yellow]")
        return

    config = json.loads(config_path.read_text())
    db_url = config.get("db_url", "")
    if not db_url or "postgresql" not in db_url:
        return

    sync_url = db_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    try:
        import psycopg2
        conn = psycopg2.connect(sync_url)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.service_accounts (id, key_id, email, project_id, public_key_pem, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (key_id) DO UPDATE SET public_key_pem = EXCLUDED.public_key_pem
            """,
            (str(uuid.uuid4()), key_id, email, project_id, public_pem, datetime.now(timezone.utc)),
        )
        conn.commit()
        cur.close()
        conn.close()
        console.print(f"[green]Service account registered in DB: {email}[/green]")
    except Exception as e:
        console.print(f"[yellow]Could not register in DB: {e}[/yellow]")
