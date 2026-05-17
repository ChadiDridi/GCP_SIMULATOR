from pathlib import Path
from pydantic_settings import BaseSettings

_ALL_SERVICES = [
    "gcs", "pubsub", "bigquery", "firestore",
    "cloudsql", "spanner", "bigtable", "memorystore",
    "cloudrun", "gce", "vpc", "lb",
    "secretmanager", "dataflow", "dataform",
    "iam", "dns", "scheduler", "tasks",
]


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:simulator-pg-pass@localhost:5432/gcp_simulator"
    project_id: str = "local-dev"
    dev_token: str = "dev-token"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 9099
    enabled_services: str = "gcs,pubsub,bigquery,firestore"
    sqlite_mode: bool = False
    data_dir: str = str(Path.home() / ".gcp-sim")
    redis_url: str = "redis://localhost:6379"
    pg_container_port: int = 5432
    redis_container_port: int = 6379

    model_config = {"env_prefix": "GCP_SIM_"}

    @property
    def enabled_services_list(self) -> list[str]:
        if self.enabled_services.strip().lower() == "all":
            return list(_ALL_SERVICES)
        return [s.strip() for s in self.enabled_services.split(",") if s.strip()]

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).expanduser()


settings = Settings()
