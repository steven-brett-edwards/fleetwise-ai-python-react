"""Async engine + session factory + FastAPI dependency.

One engine + `async_sessionmaker` per process, resolved at startup. The
`get_session` dependency yields an `AsyncSession` that FastAPI scopes to
the request lifetime and closes automatically.

The `DATABASE_URL` default is `sqlite+aiosqlite:///./fleetwise.db` for
local dev; Render overrides it to point at a volume-mounted path in Phase
6 so the database survives container restarts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from fleetwise.domain.entities import Base
from fleetwise.settings import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazy-init the engine; reusing one engine per process is the supported pattern."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Use via `session: AsyncSession = Depends(get_session)`."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """Create tables if missing. Called from the FastAPI startup hook."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def reset_engine() -> None:
    """Test hook: drop the cached engine so a fresh per-test URL is picked up."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
