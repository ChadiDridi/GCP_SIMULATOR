from fastapi import APIRouter
from gcp_simulator.app.routers.iam.roles import router as roles_router
from gcp_simulator.app.routers.iam.bindings import router as bindings_router
from gcp_simulator.app.routers.iam.service_accounts_iam import router as service_accounts_router

router = APIRouter()
router.include_router(roles_router)
router.include_router(bindings_router)
router.include_router(service_accounts_router)
