"""End-to-end RAG test against a real Chroma with fake embeddings.

Exercises the whole pipeline in isolation:
ingestion → vector store → `search_fleet_documentation` tool.

Fake embeddings are deterministic -- a tiny hash-based vector per text.
This isn't a retrieval-quality test; it's a wiring test. Retrieval
quality is implicitly validated by the chunker unit tests and a live
smoke check against the deployed agent.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest_asyncio
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from fleetwise.ai.rag.ingestion import ingest_if_empty
from fleetwise.ai.tools._retrieval import set_vector_store
from fleetwise.ai.tools.document_search import search_fleet_documentation


class _FakeEmbeddings(Embeddings):
    """Hash-based 16-dim embeddings -- deterministic, reproducible, fast.

    Not semantically meaningful, but that's fine: this test only asserts
    that ingest-then-search round-trips through Chroma end-to-end and the
    tool's output matches the .NET wire shape.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    @staticmethod
    def _vec(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # 16 floats in [0, 1). Chroma accepts any dimensionality as long
        # as documents and queries agree.
        return [b / 255.0 for b in digest[:16]]


@pytest_asyncio.fixture
async def populated_store() -> AsyncIterator[Chroma]:
    """Real Chroma, in-tmpdir persistence, two markdown files ingested."""
    with TemporaryDirectory() as persist_dir, TemporaryDirectory() as docs_dir:
        doc_root = Path(docs_dir)
        (doc_root / "fuel-policy.md").write_text(
            "# Fuel Policy\n\n## Anti-idling\nVehicles must shut off after 5 minutes idle.\n",
            encoding="utf-8",
        )
        (doc_root / "safety.md").write_text(
            "# Safety\n\n## PPE\nSafety glasses required in shop areas.\n",
            encoding="utf-8",
        )

        store = Chroma(
            collection_name="test-docs",
            embedding_function=_FakeEmbeddings(),
            persist_directory=persist_dir,
        )

        written = await ingest_if_empty(store, str(doc_root))
        assert written > 0  # sanity: both files produced chunks

        yield store


async def test_ingest_then_search_returns_formatted_banner(populated_store: Chroma) -> None:
    set_vector_store(populated_store)
    try:
        out = cast(
            str,
            await search_fleet_documentation.ainvoke({"query": "anti-idling policy", "top_k": 2}),
        )
    finally:
        set_vector_store(None)

    # Banner + source-tagged results, same shape the .NET plugin emits.
    assert 'Found the following relevant documentation for: "anti-idling policy"' in out
    assert "--- Source: " in out
    assert "(relevance:" in out


async def test_ingest_is_idempotent_on_populated_collection(populated_store: Chroma) -> None:
    # A second ingest against the same store should be a no-op -- the
    # emptiness probe returns hits, so we return 0 without re-embedding.
    with TemporaryDirectory() as docs_dir:
        written = await ingest_if_empty(populated_store, docs_dir)
        assert written == 0


async def test_search_tool_returns_notice_when_store_missing() -> None:
    # No registered store (Phase 3-style deployment). The tool should
    # give the LLM a plain-language notice rather than raising.
    set_vector_store(None)
    out = cast(str, await search_fleet_documentation.ainvoke({"query": "anything"}))
    assert "not available" in out


async def test_search_tool_returns_no_match_message_when_collection_empty() -> None:
    # Fresh empty Chroma -> search finds nothing -> friendly message.
    with TemporaryDirectory() as persist_dir:
        store = Chroma(
            collection_name="empty-docs",
            embedding_function=_FakeEmbeddings(),
            persist_directory=persist_dir,
        )
        set_vector_store(store)
        try:
            out = cast(
                str,
                await search_fleet_documentation.ainvoke({"query": "ghosts"}),
            )
        finally:
            set_vector_store(None)

    assert "No documentation found" in out
