from fastapi import APIRouter
from gcp_simulator.app.routers.dataform.repositories import router as repositories_router
from gcp_simulator.app.routers.dataform.workspaces import router as workspaces_router

router = APIRouter()
router.include_router(repositories_router)
router.include_router(workspaces_router)
