"""Phase 0 smoke test: GET /api/health returns 200.

Uses httpx.AsyncClient with ASGITransport so the FastAPI app is exercised
in-process, no network, no uvicorn. This is the template every subsequent
integration test will follow.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from fleetwise.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
