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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor so FastAPI dependencies don't re-read env on every request."""
    return Settings()
