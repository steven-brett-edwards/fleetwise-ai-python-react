"""Unit tests for the chat rate-limit ASGI middleware.

The middleware is wrapped around a trivial inner ASGI app and driven
through httpx's ASGITransport -- full control over the limit and the
client identity headers without touching the real app fixtures.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from fleetwise.api.rate_limit import ChatRateLimitMiddleware


async def _ok_app(scope: Any, receive: Any, send: Any) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


def _client(limit: int) -> AsyncClient:
    middleware = ChatRateLimitMiddleware(_ok_app, limit_per_minute=limit)
    return AsyncClient(transport=ASGITransport(app=middleware), base_url="http://test")


async def test_requests_within_limit_pass_through() -> None:
    async with _client(limit=3) as client:
        for _ in range(3):
            res = await client.post("/api/chat")
            assert res.status_code == 200


async def test_request_over_limit_gets_429_with_retry_after() -> None:
    async with _client(limit=2) as client:
        for _ in range(2):
            assert (await client.post("/api/chat")).status_code == 200

        res = await client.post("/api/chat")
        assert res.status_code == 429
        assert res.headers["retry-after"] == "60"
        assert "Rate limit" in res.json()["detail"]


async def test_streaming_route_is_also_limited() -> None:
    async with _client(limit=1) as client:
        assert (await client.post("/api/chat/stream")).status_code == 200
        assert (await client.post("/api/chat/stream")).status_code == 429


async def test_non_chat_paths_are_never_limited() -> None:
    async with _client(limit=1) as client:
        for _ in range(5):
            res = await client.get("/api/vehicles")
            assert res.status_code == 200


async def test_clients_are_partitioned_by_forwarded_for_first_hop() -> None:
    # Render's proxy prepends the real client to X-Forwarded-For; two
    # different first hops must count against separate windows, and the
    # rest of the hop list must be ignored.
    async with _client(limit=1) as client:
        first = {"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
        second = {"X-Forwarded-For": "198.51.100.9, 10.0.0.1"}

        assert (await client.post("/api/chat", headers=first)).status_code == 200
        assert (await client.post("/api/chat", headers=first)).status_code == 429
        # A different client is unaffected by the first one's exhaustion.
        assert (await client.post("/api/chat", headers=second)).status_code == 200


async def test_window_resets_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    middleware = ChatRateLimitMiddleware(_ok_app, limit_per_minute=1)
    fake_now = 1000.0
    monkeypatch.setattr("fleetwise.api.rate_limit.time.monotonic", lambda: fake_now)

    async with AsyncClient(
        transport=ASGITransport(app=middleware), base_url="http://test"
    ) as client:
        assert (await client.post("/api/chat")).status_code == 200
        assert (await client.post("/api/chat")).status_code == 429

        fake_now += 61.0
        assert (await client.post("/api/chat")).status_code == 200


async def test_stale_entries_are_pruned_once_table_is_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = ChatRateLimitMiddleware(_ok_app, limit_per_minute=5)
    monkeypatch.setattr("fleetwise.api.rate_limit._MAX_TRACKED_CLIENTS", 2)
    fake_now = 1000.0
    monkeypatch.setattr("fleetwise.api.rate_limit.time.monotonic", lambda: fake_now)

    async with AsyncClient(
        transport=ASGITransport(app=middleware), base_url="http://test"
    ) as client:
        await client.post("/api/chat", headers={"X-Forwarded-For": "203.0.113.1"})
        await client.post("/api/chat", headers={"X-Forwarded-For": "203.0.113.2"})
        assert len(middleware._hits) == 2

        # Both prior windows expire; the next distinct client triggers a
        # prune instead of growing the table.
        fake_now += 61.0
        await client.post("/api/chat", headers={"X-Forwarded-For": "203.0.113.3"})
        assert len(middleware._hits) == 1
