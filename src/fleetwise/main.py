"""FastAPI app factory.

Startup hook handles two things in order: create tables (`init_db`) and
seed from JSON dumps if the DB is empty (`seed_if_empty`). Both are
idempotent, so a warm container restart is a no-op.

Routers land under `/api` as each phase adds them. Phase 0 shipped the
health endpoint; Phase 2 mounts the resource routers (vehicles,
maintenance, work-orders) and wires CORS for the browser clients.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fleetwise.ai.agent import agent_lifespan
from fleetwise.api import (
    chat as chat_api,
    maintenance as maintenance_api,
    vehicles as vehicles_api,
    work_orders as work_orders_api,
)
from fleetwise.data.db import get_session_factory, init_db
from fleetwise.data.seed import seed_if_empty
from fleetwise.settings import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create tables + seed demo data, build the LangGraph agent, hand control back.

    The agent bundle is held on `app.state.agent` for the lifetime of the
    process -- chat handlers pull it via the `AgentDep` dependency rather
    than rebuilding the graph per request. `agent_lifespan` also owns the
    `AsyncSqliteSaver`'s underlying aiosqlite connection; exiting the
    `async with` on shutdown closes it cleanly.
    """
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        await seed_if_empty(session)

    settings = get_settings()
    async with agent_lifespan(settings) as agent:
        app.state.agent = agent
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    app.include_router(vehicles_api.router, prefix="/api")
    app.include_router(maintenance_api.router, prefix="/api")
    app.include_router(work_orders_api.router, prefix="/api")
    app.include_router(chat_api.router, prefix="/api")

    return app


app = create_app()
