"""Vector-store registry for RAG tools.

The document-search tool needs a Chroma handle but -- like the DB
session factory -- it's invoked outside the FastAPI request scope, so
dependency injection isn't an option. The app lifespan registers the
store here once at startup and `search_fleet_documentation` reads it
via `get_vector_store()`.

Tests inject a fake store the same way.
"""

from __future__ import annotations

from typing import Any

_vector_store: Any | None = None


def set_vector_store(store: Any | None) -> None:
    """Called by the app lifespan (or tests) to register the live store."""
    global _vector_store
    _vector_store = store


def get_vector_store() -> Any | None:
    """Current store, or None if RAG is disabled / not yet initialized."""
    return _vector_store
