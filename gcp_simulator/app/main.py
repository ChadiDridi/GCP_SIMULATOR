from contextlib import asynccontextmanager
from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gcp_simulator.app.config import settings
from gcp_simulator.app.middleware.auth import AuthMiddleware

# Service name → (module_path, router_attr)
_SERVICE_REGISTRY = {
    "gcs":           ("gcp_simulator.app.routers.gcs.router", "router"),
    "pubsub":        ("gcp_simulator.app.routers.pubsub.router", "router"),
    "bigquery":      ("gcp_simulator.app.routers.bigquery.router", "router"),
    "firestore":     ("gcp_simulator.app.routers.firestore.router", "router"),
    "cloudsql":      ("gcp_simulator.app.routers.cloudsql.router", "router"),
    "spanner":       ("gcp_simulator.app.routers.spanner.router", "router"),
    "bigtable":      ("gcp_simulator.app.routers.bigtable.router", "router"),
    "memorystore":   ("gcp_simulator.app.routers.memorystore.router", "router"),
    "cloudrun":      ("gcp_simulator.app.routers.cloudrun.router", "router"),
    "gce":           ("gcp_simulator.app.routers.gce.router", "router"),
    "vpc":           ("gcp_simulator.app.routers.vpc.router", "router"),
    "lb":            ("gcp_simulator.app.routers.loadbalancer.router", "router"),
    "secretmanager": ("gcp_simulator.app.routers.secretmanager.router", "router"),
    "dataflow":      ("gcp_simulator.app.routers.dataflow.router", "router"),
    "dataform":      ("gcp_simulator.app.routers.dataform.router", "router"),
    "iam":           ("gcp_simulator.app.routers.iam.router", "router"),
    "dns":           ("gcp_simulator.app.routers.dns.router", "router"),
    "scheduler":     ("gcp_simulator.app.routers.scheduler.router", "router"),
    "tasks":         ("gcp_simulator.app.routers.tasks.router", "router"),
    "alloydb":       ("gcp_simulator.app.routers.alloydb.router", "router"),
    "dms":           ("gcp_simulator.app.routers.dms.router", "router"),
    "datastream":    ("gcp_simulator.app.routers.datastream.router", "router"),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup Cloud Run containers on shutdown
    if "cloudrun" in settings.enabled_services_list:
        try:
            from gcp_simulator.cli.docker_manager import stop_container, docker_available
            from gcp_simulator.app.db.engine import AsyncSessionLocal
            from gcp_simulator.app.models.cloudrun import CloudRunService
            from sqlalchemy import select
            if docker_available():
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(CloudRunService).where(CloudRunService.container_id.isnot(None))
                    )
                    for svc in result.scalars().all():
                        try:
                            import asyncio
                            await asyncio.to_thread(stop_container, svc.container_id)
                        except Exception:
                            pass
        except Exception:
            pass


app = FastAPI(
    title="GCP Simulator",
    description="Local GCP services simulator — like Azurite for Azure",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 is always mounted (needed for auth)
from gcp_simulator.app.routers.oauth2 import router as oauth2_router
app.include_router(oauth2_router)

# Dynamically mount only enabled services
enabled = settings.enabled_services_list
for svc_name in enabled:
    if svc_name in _SERVICE_REGISTRY:
        mod_path, attr = _SERVICE_REGISTRY[svc_name]
        try:
            mod = import_module(mod_path)
            router = getattr(mod, attr)
            app.include_router(router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load service '{svc_name}': {e}")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "services": enabled,
        "version": "2.0.0",
    }


@app.get("/")
async def root():
    return {
        "name": "GCP Simulator",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "enabled_services": enabled,
    }
