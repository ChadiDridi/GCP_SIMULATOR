import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Must be set before any app module is imported so Settings picks them up
os.environ.setdefault("GCP_SIM_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GCP_SIM_ENABLED_SERVICES", "gcs,pubsub,bigquery,firestore")

from gcp_simulator.app.db.engine import Base, get_db  # noqa: E402
from gcp_simulator.app.main import app  # noqa: E402

# All PostgreSQL schemas used in the models — map to None so SQLite ignores them
_ALL_SCHEMAS = [
    "auth", "gcs", "pubsub", "bigquery", "firestore", "bq_data",
    "cloudsql", "spanner", "bigtable", "memorystore", "cloudrun",
    "gce", "vpc", "loadbalancer", "secretmanager", "dataflow",
    "dataform", "iam", "dns", "scheduler", "tasks",
    "alloydb", "dms", "datastream",
]
_SCHEMA_TRANSLATE = {s: None for s in _ALL_SCHEMAS}

_TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    echo=False,
)
# Separate engine with schema_translate_map so all queries on it strip schemas
_TEST_ENGINE_TRANSLATED = _TEST_ENGINE.execution_options(
    schema_translate_map=_SCHEMA_TRANSLATE
)
_TestSession = async_sessionmaker(
    _TEST_ENGINE_TRANSLATED, class_=AsyncSession, expire_on_commit=False
)


async def _get_test_db():
    async with _TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True, scope="session")
async def _create_tables():
    """Create ORM tables in the in-memory SQLite DB (schemas stripped for compatibility)."""
    import gcp_simulator.app.models.auth  # noqa: F401
    import gcp_simulator.app.models.gcs  # noqa: F401
    import gcp_simulator.app.models.pubsub  # noqa: F401
    import gcp_simulator.app.models.bigquery  # noqa: F401
    import gcp_simulator.app.models.firestore  # noqa: F401
    import gcp_simulator.app.models.alloydb  # noqa: F401
    import gcp_simulator.app.models.dms  # noqa: F401
    import gcp_simulator.app.models.datastream  # noqa: F401

    async with _TEST_ENGINE.begin() as conn:
        translated = await conn.execution_options(schema_translate_map=_SCHEMA_TRANSLATE)
        await translated.run_sync(Base.metadata.create_all)
    yield
    async with _TEST_ENGINE.begin() as conn:
        translated = await conn.execution_options(schema_translate_map=_SCHEMA_TRANSLATE)
        await translated.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(_create_tables):
    app.dependency_overrides[get_db] = _get_test_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer dev-token"},
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
