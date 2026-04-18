"""Shared pytest fixtures.

Every DB test gets its own in-memory aiosqlite engine with a fresh schema
and seeded fleet. The session fixture yields an `AsyncSession` bound to
that engine; tearing down the engine between tests keeps tests isolated
without paying for per-test file I/O.

The `app` + `client` fixtures override FastAPI's `get_session` dependency
so the API routes (added in Phase 2+) exercise the same in-memory DB.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fleetwise.data.db import get_session
from fleetwise.data.seed import seed_if_empty
from fleetwise.domain.entities import Base
from fleetwise.main import create_app


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory DB + seeded fleet, per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as seed_session:
        await seed_if_empty(seed_session)

    async with factory() as test_session:
        yield test_session

    await engine.dispose()


@pytest_asyncio.fixture
async def app(session: AsyncSession) -> AsyncIterator[FastAPI]:
    """FastAPI app with `get_session` overridden to yield the test session.

    Overriding the dependency (rather than replacing the engine) means
    each test operates on the exact same in-memory state the `session`
    fixture exposes -- assertions touching both the DB directly and the
    HTTP surface see consistent data.
    """
    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_session
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def expected_seed_counts() -> dict[str, int]:
    """Ground truth from the .NET SQLite dump -- if seed data drifts, tests catch it."""
    return {
        "vehicles": 35,
        "parts": 45,
        "work_orders": 36,
        "maintenance_records": 163,
        "maintenance_schedules": 54,
    }
