"""Application settings loaded from environment variables.

One config source of truth — everything the app needs is a field on this
model. `.env.example` at the repo root documents every knob. Future phases
add database URLs, LLM provider keys, CORS origins, etc.; for Phase 0 we
keep it minimal so the hello-world deploy has one less thing to go wrong.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    # Just Works. Production origins come from the Render env var as a
    # comma-separated list; the validator below accepts either CSV (what
    # humans write in env-var UIs) or JSON (what pydantic-settings would
    # natively parse for a complex-typed field).
    cors_allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:4200",
        "http://localhost:5173",
    ]

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_csv_origins(cls, raw: object) -> object:
        """Accept `a,b,c` or `["a","b","c"]` or a real list.

        `NoDecode` on the field disables pydantic-settings' own JSON
        attempt, so the env source hands us the raw string. We do both
        formats here: JSON-looking input (starts with `[`) is parsed as
        JSON; everything else is treated as CSV. Real lists (from the
        default or init kwargs) pass through unchanged.
        """
        if isinstance(raw, str):
            stripped = raw.lstrip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in raw.split(",") if item.strip()]
        return raw

    # --- AI / LangGraph configuration -------------------------------------
    # Flip between Anthropic (hosted demo default), OpenAI (fallback), and
    # Ollama (local-first, no API key). The factory in `ai.providers`
    # matches on this literal.
    ai_provider: Literal["anthropic", "openai", "ollama"] = "anthropic"

    # Anthropic (default for the hosted demo).
    anthropic_api_key: str | None = None
    anthropic_chat_model: str = "claude-sonnet-4-5"

    # OpenAI — used as a chat fallback, and as the embedding provider in
    # Phase 5 even when chat is Anthropic (Anthropic has no embeddings API).
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"

    # Ollama — local, free, no key. Default endpoint matches the out-of-box
    # `ollama serve` listener.
    ollama_endpoint: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"

    # LangGraph checkpointer DB. Persistent conversation history across
    # restarts -- a free upgrade over the .NET `ConcurrentDictionary`. On
    # Render this points at the same volume-mounted directory the fleet DB
    # uses (e.g. `/app/data/checkpoints.db`).
    checkpoint_db_path: str = "./checkpoints.db"

    # --- RAG (Phase 5) ----------------------------------------------------
    # Directory of markdown SOP documents to ingest on startup. Five files
    # ported verbatim from the .NET `data/documents/` tree.
    documents_dir: str = "./data/documents"

    # Where Chroma writes its SQLite + hnsw index. On Render this points
    # inside the same volume as the fleet DB and checkpoint store, so the
    # collection survives restarts and ingestion becomes a one-shot cost.
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "fleet-documents"

    # Embedding model + provider. Anthropic has no embeddings endpoint, so
    # the chat provider and embedding provider are configured independently.
    # `auto` picks openai if an OPENAI_API_KEY is set, else ollama, else
    # disables RAG (the agent won't advertise `search_fleet_documentation`).
    embedding_provider: Literal["auto", "openai", "ollama", "disabled"] = "auto"
    openai_embedding_model: str = "text-embedding-3-small"
    ollama_embedding_model: str = "nomic-embed-text"

    # --- Frontend (Phase 9) -----------------------------------------------
    # Absolute path to the built React SPA (`frontend/dist`). When unset,
    # `main._mount_frontend` walks up from the source tree to find the
    # dev-build location. In Docker the image bakes the build into
    # `/app/frontend/dist` and this env var points there explicitly so the
    # resolution doesn't depend on cwd.
    frontend_dist_dir: Path | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor so FastAPI dependencies don't re-read env on every request."""
    return Settings()
