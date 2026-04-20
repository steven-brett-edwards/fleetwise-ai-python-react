"""Application settings loaded from environment variables.

One config source of truth — everything the app needs is a field on this
model. `.env.example` at the repo root documents every knob. Future phases
add database URLs, LLM provider keys, CORS origins, etc.; for Phase 0 we
keep it minimal so the hello-world deploy has one less thing to go wrong.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FleetWise AI (Python)"
    environment: str = "development"

    # Async SQLAlchemy URL. Default lands the dev DB next to the repo root;
    # Render mounts a persistent volume at /app/data and overrides this.
    database_url: str = "sqlite+aiosqlite:///./fleetwise.db"

    # CORS allow-list for the browser clients. Angular dev server defaults
    # to :4200, Vite to :5173 -- both are in the default so `npm run dev`
    # Just Works. Production origins come from the Render env var (comma-
    # separated list; pydantic-settings parses it into `list[str]` via
    # its built-in JSON/CSV inference on collection-typed fields).
    cors_allowed_origins: list[str] = [
        "http://localhost:4200",
        "http://localhost:5173",
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor so FastAPI dependencies don't re-read env on every request."""
    return Settings()
