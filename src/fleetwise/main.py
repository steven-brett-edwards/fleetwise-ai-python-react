"""FastAPI app factory.

Startup hook handles two things in order: create tables (`init_db`) and
seed from JSON dumps if the DB is empty (`seed_if_empty`). Both are
idempotent, so a warm container restart is a no-op.

Routers land under `/api` as each phase adds them. Phase 0 shipped the
health endpoint; Phase 2 mounts the resource routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fleetwise.data.db import get_session_factory, init_db
from fleetwise.data.seed import seed_if_empty
from fleetwise.settings import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create tables + seed demo data on startup; dispose cleanly on shutdown."""
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        await seed_if_empty(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=_lifespan)

    @app.get("/api/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    return app


app = create_app()
