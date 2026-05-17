from fastapi import APIRouter
from gcp_simulator.app.routers.secretmanager.secrets import router as secrets_router

router = APIRouter()
router.include_router(secrets_router)
