from fastapi import APIRouter
from gcp_simulator.app.routers.cloudrun.services import router as services_router
from gcp_simulator.app.routers.cloudrun.proxy import router as proxy_router

router = APIRouter()
router.include_router(services_router)
router.include_router(proxy_router)
