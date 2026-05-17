from fastapi import APIRouter
from gcp_simulator.app.routers.bigtable.instances import router as instances_router
from gcp_simulator.app.routers.bigtable.tables import router as tables_router
from gcp_simulator.app.routers.bigtable.data import router as data_router

router = APIRouter()
router.include_router(instances_router)
router.include_router(tables_router)
router.include_router(data_router)
