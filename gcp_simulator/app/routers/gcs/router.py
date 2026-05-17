from fastapi import APIRouter
from gcp_simulator.app.routers.gcs.buckets import router as buckets_router
from gcp_simulator.app.routers.gcs.objects import router as objects_router

router = APIRouter()
router.include_router(buckets_router)
router.include_router(objects_router)
