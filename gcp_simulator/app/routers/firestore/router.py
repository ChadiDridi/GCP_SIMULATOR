from fastapi import APIRouter
from gcp_simulator.app.routers.firestore.documents import router as documents_router

router = APIRouter()
router.include_router(documents_router)
