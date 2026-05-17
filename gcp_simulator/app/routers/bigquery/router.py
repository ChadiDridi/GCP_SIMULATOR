from fastapi import APIRouter
from gcp_simulator.app.routers.bigquery.datasets import router as datasets_router
from gcp_simulator.app.routers.bigquery.tables import router as tables_router
from gcp_simulator.app.routers.bigquery.tabledata import router as tabledata_router
from gcp_simulator.app.routers.bigquery.jobs import router as jobs_router

router = APIRouter()
router.include_router(datasets_router)
router.include_router(tables_router)
router.include_router(tabledata_router)
router.include_router(jobs_router)
