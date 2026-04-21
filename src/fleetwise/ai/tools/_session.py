"""DB session helper for tool implementations.

Tools are invoked by the LangGraph agent outside the FastAPI request
scope, so they can't use the `get_session` dependency. They grab a
session from the module-level `get_session_factory()` singleton instead.

In tests we monkeypatch `fleetwise.data.db._session_factory` (via a
`tool_session` conftest fixture) so tool calls hit the same in-memory
engine the `session` fixture uses for direct DB assertions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.db import get_session_factory


@asynccontextmanager
async def tool_session() -> AsyncIterator[AsyncSession]:
    """Open a short-lived session for a tool invocation."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
