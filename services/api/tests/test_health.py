import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.anyio
async def test_health_endpoints():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Check /v1/health
        res1 = await ac.get("/v1/health")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "ok"
        assert "env" in data1
        assert "version" in data1

        # Check /v1/healthz
        res2 = await ac.get("/v1/healthz")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ok"
