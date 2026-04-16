"""
Test suite for the Background Job Processor API.

Run with:
    pytest tests/ -v
"""
import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base, get_db
from app.main import app

# ── In-memory test database ───────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, future=True)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        from app.models import job  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_submit_job(client: AsyncClient):
    payload = {"name": "test-job", "payload": {"key": "value"}, "priority": 2}
    resp = await client.post("/api/v1/jobs/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["name"] == "test-job"
    assert "id" in data
    return data["id"]


@pytest.mark.asyncio
async def test_submit_job_minimal(client: AsyncClient):
    resp = await client.post("/api/v1/jobs/", json={"name": "minimal-job"})
    assert resp.status_code == 201
    assert resp.json()["payload"] is None


@pytest.mark.asyncio
async def test_submit_job_invalid_name(client: AsyncClient):
    resp = await client.post("/api/v1/jobs/", json={"name": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_job(client: AsyncClient):
    create_resp = await client.post("/api/v1/jobs/", json={"name": "get-test"})
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/jobs/nonexistent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_jobs(client: AsyncClient):
    # Submit a couple of jobs
    for i in range(3):
        await client.post("/api/v1/jobs/", json={"name": f"list-job-{i}"})

    resp = await client.get("/api/v1/jobs/")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status(client: AsyncClient):
    resp = await client.get("/api/v1/jobs/?status=pending")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_jobs_pagination(client: AsyncClient):
    resp = await client.get("/api/v1/jobs/?skip=0&limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2


@pytest.mark.asyncio
async def test_cancel_pending_job(client: AsyncClient):
    create_resp = await client.post("/api/v1/jobs/", json={"name": "cancel-test"})
    job_id = create_resp.json()["id"]

    cancel_resp = await client.delete(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    assert "cancelled" in cancel_resp.json()["message"]

    status_resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_already_cancelled_job(client: AsyncClient):
    create_resp = await client.post("/api/v1/jobs/", json={"name": "double-cancel"})
    job_id = create_resp.json()["id"]

    await client.delete(f"/api/v1/jobs/{job_id}/cancel")
    resp = await client.delete(f"/api/v1/jobs/{job_id}/cancel")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cancel_nonexistent_job(client: AsyncClient):
    resp = await client.delete("/api/v1/jobs/ghost-id/cancel")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stats_endpoint(client: AsyncClient):
    resp = await client.get("/api/v1/jobs/stats")
    assert resp.status_code == 200
    data = resp.json()
    for field in ("total", "pending", "in_progress", "completed", "failed", "cancelled"):
        assert field in data


@pytest.mark.asyncio
async def test_priority_range_validation(client: AsyncClient):
    resp = await client.post("/api/v1/jobs/", json={"name": "bad-priority", "priority": 99})
    assert resp.status_code == 422
