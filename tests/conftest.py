import pytest
from httpx import AsyncClient, ASGITransport
from gcp_simulator.app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer dev-token"},
    ) as c:
        yield c
