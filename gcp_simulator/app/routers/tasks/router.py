from fastapi import APIRouter
from gcp_simulator.app.routers.tasks.queues import router as queues_router

router = APIRouter()
router.include_router(queues_router)
