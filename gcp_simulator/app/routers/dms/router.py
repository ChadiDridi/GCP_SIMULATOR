from fastapi import APIRouter
from gcp_simulator.app.routers.dms.connection_profiles import router as connection_profiles_router
from gcp_simulator.app.routers.dms.migration_jobs import router as migration_jobs_router

router = APIRouter()
router.include_router(connection_profiles_router)
router.include_router(migration_jobs_router)
