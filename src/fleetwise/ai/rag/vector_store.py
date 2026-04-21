"""Chroma persistent vector store factory.

One function, one choice that matters: the `persist_directory`. On
Render this points inside the same mounted disk as the fleet DB and
checkpoint store (`/app/data/chroma`), so the embedded collection
survives restarts and re-ingestion is a no-op after the first boot.

Chroma stores its data as a sqlite3 + hnsw index under that directory;
no server process, no network hop, no cost. Good enough for five SOP
documents and a portfolio demo.
"""

from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from fleetwise.settings import Settings


def build_vector_store(embeddings: Embeddings, settings: Settings) -> Chroma:
    """Open (or create) the persistent collection at the configured path.

    `Chroma` is idempotent on construction -- calling it twice against
    the same `persist_directory` opens the existing collection rather
    than clobbering it. The ingestion layer uses that to skip work when
    the collection is already populated.
    """
    return Chroma(
        collection_name=settings.chroma_collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )
