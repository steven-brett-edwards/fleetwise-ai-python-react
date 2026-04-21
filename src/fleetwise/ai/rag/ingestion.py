"""One-shot markdown → Chroma ingestion.

Walks `settings.documents_dir/*.md`, chunks each file with the
heading-based chunker, and upserts `{filename}_{i}` into the collection.
Skips the work entirely if the collection is already populated: on
Render the collection lives on a mounted disk, and re-embedding on
every boot would cost API calls for no reason.

Chroma's LangChain wrapper is synchronous; we wrap `.add_texts` in
`asyncio.to_thread` so a slow embedding call doesn't block the event
loop during app startup. The actual per-document work is fast (five
files, a few dozen chunks total) but the pattern is worth having so
Phase 10's ETL pipeline can ingest much larger inputs the same way.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from langchain_chroma import Chroma

from fleetwise.ai.rag.chunker import chunk_by_headings

logger = logging.getLogger(__name__)


async def ingest_if_empty(vector_store: Chroma, documents_dir: str) -> int:
    """Chunk + embed every markdown file under `documents_dir` if collection is empty.

    Returns the number of chunks written (0 if the collection was already
    populated or the directory is missing). Never raises on "no documents
    to ingest" -- RAG is optional, and a missing corpus just means the
    retrieval tool has nothing to return.
    """
    # Cheap emptiness probe via the public `.get(limit=1)` API: returns
    # `{"ids": [...], ...}` and comes back with an empty list when the
    # collection has no rows. Avoids reaching into `_collection` (which
    # Pylance rightly flags as private) and avoids a similarity search.
    probe = vector_store.get(limit=1)
    if probe.get("ids"):
        logger.info("RAG collection already populated; skipping ingest")
        return 0

    root = Path(documents_dir)
    if not root.is_dir():
        logger.warning("RAG documents dir %s missing; skipping ingest", documents_dir)
        return 0

    texts: list[str] = []
    metadatas: list[dict[str, str]] = []
    ids: list[str] = []

    for path in sorted(root.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        for i, chunk in enumerate(chunk_by_headings(content)):
            texts.append(chunk)
            metadatas.append({"source": path.name})
            ids.append(f"{path.stem}_{i}")

    if not texts:
        logger.warning("No markdown files found under %s", documents_dir)
        return 0

    # `add_texts` is sync (Chroma's client is sync); offload to a worker
    # thread so the embedding HTTP call doesn't block startup.
    await asyncio.to_thread(vector_store.add_texts, texts, metadatas=metadatas, ids=ids)
    logger.info(
        "Ingested %d chunks from %d files into %s", len(texts), len(set(ids)), documents_dir
    )
    return len(texts)
