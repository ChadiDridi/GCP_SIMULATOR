from fastapi import APIRouter
from gcp_simulator.app.routers.pubsub.topics import router as topics_router
from gcp_simulator.app.routers.pubsub.subscriptions import router as subscriptions_router

router = APIRouter()
router.include_router(topics_router)
router.include_router(subscriptions_router)
