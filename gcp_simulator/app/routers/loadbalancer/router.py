from fastapi import APIRouter
from gcp_simulator.app.routers.loadbalancer.forwarding_rules import router as forwarding_rules_router
from gcp_simulator.app.routers.loadbalancer.backend_services import router as backend_services_router
from gcp_simulator.app.routers.loadbalancer.health_checks import router as health_checks_router
from gcp_simulator.app.routers.loadbalancer.url_maps import router as url_maps_router
from gcp_simulator.app.routers.loadbalancer.target_http_proxies import router as target_http_proxies_router

router = APIRouter()
router.include_router(forwarding_rules_router)
router.include_router(backend_services_router)
router.include_router(health_checks_router)
router.include_router(url_maps_router)
router.include_router(target_http_proxies_router)
