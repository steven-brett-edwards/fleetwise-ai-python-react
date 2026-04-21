"""FastAPI dependencies shared across routers.

`SessionDep` is the one every endpoint uses -- an `Annotated` alias keeps
router signatures short and gives tests a single key (`get_session`) to
override via `app.dependency_overrides`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.ai.agent import AgentBundle
from fleetwise.data.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_agent(request: Request) -> AgentBundle:
    """Return the process-wide agent bundle built by the lifespan.

    The bundle lives on `app.state.agent` for the life of the process;
    requests pull it out here rather than rebuilding the graph per call.
    """
    agent: AgentBundle | None = getattr(request.app.state, "agent", None)
    if agent is None:
        # Missing when the chat endpoint is mounted but the lifespan never
        # ran (e.g. a TestClient path that skips agent wiring). Callers
        # that need the agent should ensure the lifespan has populated it.
        raise RuntimeError(
            "Agent bundle is not initialized. The FastAPI lifespan must run "
            "before /api/chat is invoked."
        )
    return agent


AgentDep = Annotated[AgentBundle, Depends(get_agent)]
