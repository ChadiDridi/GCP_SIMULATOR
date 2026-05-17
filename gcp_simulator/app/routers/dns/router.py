from fastapi import APIRouter
from gcp_simulator.app.routers.dns.zones import router as zones_router
from gcp_simulator.app.routers.dns.record_sets import router as record_sets_router

router = APIRouter()
router.include_router(zones_router)
router.include_router(record_sets_router)
