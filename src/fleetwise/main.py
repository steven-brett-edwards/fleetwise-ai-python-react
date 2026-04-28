"""FastAPI app factory.

Startup hook handles three things in order: create tables (`init_db`),
seed from JSON dumps if the DB is empty (`seed_if_empty`), and build
the LangGraph agent bundle (which transitively opens the Chroma RAG
store and ingests SOP markdown when embeddings are available). All
steps are idempotent, so a warm container restart is a no-op.

Routers land under `/api` as each phase adds them: Phase 0 shipped
health, Phase 2 mounted vehicles / maintenance / work-orders, Phase 3
added sync chat, Phase 4 added streaming chat.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fleetwise.ai.agent import agent_lifespan
from fleetwise.api import (
    chat as chat_api,
    maintenance as maintenance_api,
    vehicles as vehicles_api,
    work_orders as work_orders_api,
)
from fleetwise.data.db import get_session_factory, init_db
from fleetwise.data.seed import seed_if_empty
from fleetwise.etl.bootstrap import ingest_inspections_if_empty
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
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as session:
        await seed_if_empty(session)
        # Phase 10: keep the deployed demo self-contained. On Render's
        # ephemeral free-tier filesystem the inspection table evaporates
        # on every cold-start; running the ETL pipeline here at boot
        # rebuilds it. CLI remains the canonical "run a real pipeline"
        # entry point.
        await ingest_inspections_if_empty(session, settings)

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

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the React SPA built into `frontend/dist` when present.

    In prod the Docker image bakes the Vite build into
    `/app/frontend/dist`; in dev the folder is absent and this function
    becomes a no-op so `uvicorn --reload` works without a frontend build.
    An SPA fallback route serves `index.html` for any unmatched GET that
    doesn't collide with `/api/*`, letting React Router own client-side
    routing.
    """
    # `main.py` is `src/fleetwise/main.py`; walk up to the repo root, then
    # resolve `frontend/dist`. Override via FRONTEND_DIST_DIR for containers
    # that bake the build into a non-standard path.
    settings = get_settings()
    dist_dir = settings.frontend_dist_dir or (
        Path(__file__).resolve().parents[2] / "frontend" / "dist"
    )
    if not dist_dir.is_dir():
        return

    # StaticFiles at a sub-path handles hashed asset files; the catch-all
    # below handles the root index.html and any client-routed URL.
    app.mount(
        "/assets",
        StaticFiles(directory=dist_dir / "assets"),
        name="spa-assets",
    )

    index_file = dist_dir / "index.html"

    @app.get("/", include_in_schema=False)
    async def spa_index() -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        return FileResponse(index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request) -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        # Never shadow /api; FastAPI's routing runs /api routes before this
        # catch-all, but if nothing matched we don't want to serve index.html
        # in place of a genuine 404 on an API route.
        if full_path.startswith("api/") or request.url.path.startswith("/api"):
            raise HTTPException(status_code=404)
        # Let real files under dist (e.g. favicon.ico) serve directly.
        candidate = dist_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


app = create_app()
