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
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from fleetwise.data import db as db_module
from fleetwise.data.db import get_session
from fleetwise.data.seed import seed_if_empty
from fleetwise.domain.entities import Base
from fleetwise.main import create_app


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Fresh in-memory aiosqlite engine + seeded fleet, per test.

    Split out of `session` so the tool-session fixture can reuse the same
    engine. The engine lives for one test, shared across any sessions the
    test opens (HTTP-layer session via `get_session`, direct session via
    the `session` fixture, and tool-layer sessions via `tool_session`).
    """
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(eng, expire_on_commit=False, autoflush=False)
    async with factory() as seed_session:
        await seed_if_empty(seed_session)

    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Fresh session against the per-test in-memory engine."""
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as test_session:
        yield test_session


@pytest_asyncio.fixture
async def tool_session_factory(
    engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Monkeypatch the db-module session factory to the per-test engine.

    Tool implementations open their own session via `tool_session()` --
    which reads `fleetwise.data.db.get_session_factory()` -- because they
    run outside the FastAPI request scope. Tests that exercise tools
    directly (no HTTP) need the factory to point at the same in-memory
    DB the `engine` fixture seeded. Swap the module-level singletons
    here, restore on teardown so each test starts clean.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    original_factory = db_module._session_factory
    original_engine = db_module._engine
    db_module._session_factory = factory
    db_module._engine = engine
    try:
        yield factory
    finally:
        db_module._session_factory = original_factory
        db_module._engine = original_engine


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
