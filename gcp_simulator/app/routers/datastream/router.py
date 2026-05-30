from fastapi import APIRouter
from gcp_simulator.app.routers.datastream.connection_profiles import router as connection_profiles_router
from gcp_simulator.app.routers.datastream.private_connections import router as private_connections_router
from gcp_simulator.app.routers.datastream.streams import router as streams_router

router = APIRouter()
router.include_router(connection_profiles_router)
router.include_router(private_connections_router)
router.include_router(streams_router)
