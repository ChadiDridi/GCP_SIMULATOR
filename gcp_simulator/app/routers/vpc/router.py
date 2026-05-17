from fastapi import APIRouter
from gcp_simulator.app.routers.vpc.networks import router as networks_router
from gcp_simulator.app.routers.vpc.subnets import router as subnets_router
from gcp_simulator.app.routers.vpc.firewalls import router as firewalls_router

router = APIRouter()
router.include_router(networks_router)
router.include_router(subnets_router)
router.include_router(firewalls_router)
