"""FastAPI app factory.

Phase 0: just a health endpoint. The app factory pattern is overkill for
one route, but it's what every subsequent phase will build on — routers
mounted under `/api`, CORS middleware, startup hooks for DB seed and RAG
ingestion — so we establish the shape now.
"""

from fastapi import FastAPI

from fleetwise.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
