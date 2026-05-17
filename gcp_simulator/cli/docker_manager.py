"""Manages Docker containers for PostgreSQL, Redis, Cloud SQL instances, and Cloud Run services."""

import time
import subprocess
from pathlib import Path
from typing import Optional

_docker_client = None


def _client():
    global _docker_client
    if _docker_client is None:
        import docker
        _docker_client = docker.from_env()
    return _docker_client


def docker_available() -> bool:
    try:
        _client().ping()
        return True
    except Exception:
        return False


# ── PostgreSQL ────────────────────────────────────────────────────────────────

PG_CONTAINER = "gcp-sim-postgres"
PG_IMAGE = "postgres:15-alpine"


def ensure_postgres(data_dir: Path, pg_port: int = 5432, password: str = "simulator-pg-pass") -> str:
    """Start PostgreSQL container if not running. Returns async DB URL."""
    client = _client()
    try:
        container = client.containers.get(PG_CONTAINER)
        if container.status != "running":
            container.start()
            _wait_postgres(pg_port, password)
        return _pg_url(pg_port, password)
    except Exception:
        pass

    data_dir.mkdir(parents=True, exist_ok=True)
    pg_data = data_dir / "pg-data"
    pg_data.mkdir(exist_ok=True)

    client.containers.run(
        PG_IMAGE,
        name=PG_CONTAINER,
        detach=True,
        remove=False,
        ports={"5432/tcp": pg_port},
        volumes={str(pg_data.resolve()): {"bind": "/var/lib/postgresql/data", "mode": "rw"}},
        environment={
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": "gcp_simulator",
            "POSTGRES_USER": "postgres",
        },
    )
    _wait_postgres(pg_port, password)
    return _pg_url(pg_port, password)


def stop_postgres(remove: bool = False):
    try:
        container = _client().containers.get(PG_CONTAINER)
        container.stop(timeout=10)
        if remove:
            container.remove(v=True)
    except Exception:
        pass


def _wait_postgres(port: int, password: str, timeout: int = 30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["pg_isready", "-h", "127.0.0.1", "-p", str(port), "-U", "postgres"],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        time.sleep(1)
    raise TimeoutError(f"PostgreSQL did not become ready on port {port} within {timeout}s")


def _pg_url(port: int, password: str) -> str:
    return f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/gcp_simulator"


# ── Redis ─────────────────────────────────────────────────────────────────────

REDIS_CONTAINER = "gcp-sim-redis"
REDIS_IMAGE = "redis:7-alpine"


def ensure_redis(data_dir: Path, redis_port: int = 6379) -> str:
    """Start Redis container if not running. Returns redis URL."""
    client = _client()
    try:
        container = client.containers.get(REDIS_CONTAINER)
        if container.status != "running":
            container.start()
            _wait_redis(container)
        return f"redis://127.0.0.1:{redis_port}"
    except Exception:
        pass

    redis_data = data_dir / "redis-data"
    redis_data.mkdir(parents=True, exist_ok=True)

    container = client.containers.run(
        REDIS_IMAGE,
        name=REDIS_CONTAINER,
        detach=True,
        remove=False,
        ports={"6379/tcp": redis_port},
        volumes={str(redis_data.resolve()): {"bind": "/data", "mode": "rw"}},
    )
    _wait_redis(container)
    return f"redis://127.0.0.1:{redis_port}"


def stop_redis(remove: bool = False):
    try:
        container = _client().containers.get(REDIS_CONTAINER)
        container.stop(timeout=5)
        if remove:
            container.remove()
    except Exception:
        pass


def _wait_redis(container, timeout: int = 15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = container.exec_run("redis-cli PING")
            if b"PONG" in result.output:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("Redis did not become ready")


# ── Generic container management (Cloud Run / Cloud SQL) ──────────────────────

def pull_image_if_missing(image: str):
    """Pull Docker image if not present locally."""
    client = _client()
    try:
        client.images.get(image)
    except Exception:
        client.images.pull(image)


def run_container(
    image: str,
    host_port: int,
    name: str,
    env: Optional[dict] = None,
    container_port: int = 8080,
) -> tuple[str, int]:
    """Run a detached container. Returns (container_id, host_port)."""
    client = _client()
    container = client.containers.run(
        image,
        name=name,
        detach=True,
        remove=False,
        ports={f"{container_port}/tcp": host_port},
        environment=env or {},
    )
    return container.id, host_port


def stop_container(container_id: str, remove: bool = True):
    try:
        container = _client().containers.get(container_id)
        container.stop(timeout=10)
        if remove:
            container.remove()
    except Exception:
        pass


def get_container_status(name: str) -> dict:
    try:
        container = _client().containers.get(name)
        return {"name": name, "status": container.status, "id": container.short_id}
    except Exception:
        return {"name": name, "status": "not_found", "id": None}


def run_cloudsql_postgres(name: str, host_port: int, data_dir: Path, password: str = "postgres") -> tuple[str, int]:
    """Spin up a dedicated PostgreSQL container for a Cloud SQL instance."""
    pg_data = data_dir / "cloudsql" / name
    pg_data.mkdir(parents=True, exist_ok=True)
    client = _client()
    container = client.containers.run(
        PG_IMAGE,
        name=f"gcp-sim-cloudsql-{name}",
        detach=True,
        remove=False,
        ports={"5432/tcp": host_port},
        volumes={str(pg_data.resolve()): {"bind": "/var/lib/postgresql/data", "mode": "rw"}},
        environment={
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": "postgres",
            "POSTGRES_USER": "postgres",
        },
    )
    _wait_postgres(host_port, password)
    return container.id, host_port


def run_cloudsql_mysql(name: str, host_port: int, data_dir: Path, password: str = "mysql") -> tuple[str, int]:
    """Spin up a MySQL container for a Cloud SQL instance."""
    mysql_data = data_dir / "cloudsql" / name
    mysql_data.mkdir(parents=True, exist_ok=True)
    client = _client()
    container = client.containers.run(
        "mysql:8",
        name=f"gcp-sim-cloudsql-mysql-{name}",
        detach=True,
        remove=False,
        ports={"3306/tcp": host_port},
        volumes={str(mysql_data.resolve()): {"bind": "/var/lib/mysql", "mode": "rw"}},
        environment={
            "MYSQL_ROOT_PASSWORD": password,
            "MYSQL_DATABASE": "mysql",
        },
    )
    # Wait for MySQL
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            result = container.exec_run(f"mysqladmin ping -uroot -p{password}")
            if b"alive" in result.output:
                return container.id, host_port
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("MySQL did not become ready")
