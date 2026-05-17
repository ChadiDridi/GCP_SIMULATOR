from fastapi import APIRouter
from gcp_simulator.app.routers.gce.instances import router as instances_router

router = APIRouter()
router.include_router(instances_router)
