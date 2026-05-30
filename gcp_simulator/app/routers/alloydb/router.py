from fastapi import APIRouter
from gcp_simulator.app.routers.alloydb.clusters import router as clusters_router
from gcp_simulator.app.routers.alloydb.instances import router as instances_router
from gcp_simulator.app.routers.alloydb.databases import router as databases_router
from gcp_simulator.app.routers.alloydb.users import router as users_router
from gcp_simulator.app.routers.alloydb.backups import router as backups_router

router = APIRouter()
router.include_router(clusters_router)
router.include_router(instances_router)
router.include_router(databases_router)
router.include_router(users_router)
router.include_router(backups_router)
