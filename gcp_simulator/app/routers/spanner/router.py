from fastapi import APIRouter
from gcp_simulator.app.routers.spanner.instances import router as instances_router
from gcp_simulator.app.routers.spanner.databases import router as databases_router
from gcp_simulator.app.routers.spanner.sessions import router as sessions_router

router = APIRouter()
router.include_router(instances_router)
router.include_router(databases_router)
router.include_router(sessions_router)
