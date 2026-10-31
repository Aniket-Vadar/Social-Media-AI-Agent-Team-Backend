import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def setup_database():
    await init_db()


async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "Socialix" in data["service"]


async def test_get_agent_roster():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        roster = data["data"]
        assert len(roster) == 5
        agent_ids = [a["id"] for a in roster]
        assert "master" in agent_ids
        assert "researcher" in agent_ids
        assert "creator" in agent_ids
        assert "scheduler" in agent_ids
        assert "analytics" in agent_ids


async def test_list_campaigns():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/campaigns")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) >= 1
        assert "name" in data["data"][0] and len(data["data"][0]["name"]) > 0



async def test_analytics_dashboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "kpis" in data["data"]
        assert "timeseries" in data["data"]
        assert "insights" in data["data"]
        assert data["data"]["kpis"]["completion_rate_percent"] > 0


async def test_agent_run_execution():

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "message": "Create 2 Instagram posts about autonomous AI agent workflows"
        }
        response = await client.post("/api/v1/runs", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "completed"
        assert len(data["data"]["plan"]) == 3
