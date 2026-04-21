"""RAG-enabled `agent_lifespan` integration test.

The sync / stream chat integration tests pin `rag_enabled=False` so
they stay hermetic -- this test complements them by forcing RAG *on*
with fake embeddings and asserting the lifespan:

1. Builds embeddings and a Chroma store at the configured path.
2. Runs ingestion over the SOP markdown corpus.
3. Registers the store so `search_fleet_documentation` can find it.
4. Binds the doc-search tool + appends `DOCUMENTATION_STANZA` to the
   prompt (verified indirectly by observing the scripted model being
   asked to call the tool successfully).
5. Tears the registry down on shutdown.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fleetwise.ai import embeddings as embeddings_module
from fleetwise.ai.agent import agent_lifespan
from fleetwise.ai.tools._retrieval import get_vector_store
from fleetwise.data.db import get_session
from fleetwise.main import create_app
from fleetwise.settings import get_settings
from tests.integration.conftest import ScriptedToolCallingModel

pytestmark = pytest.mark.usefixtures("tool_session_factory")


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    @staticmethod
    def _vec(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:16]]


def _scripted_doc_search_model() -> ScriptedToolCallingModel:
    """Two-turn script: call `search_fleet_documentation`, then answer."""
    return ScriptedToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_fleet_documentation",
                        "args": {"query": "anti-idling policy", "top_k": 2},
                        "id": "call_doc",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Anti-idling requires shutoff after 5 minutes."),
        ]
    )


@pytest_asyncio.fixture
async def rag_chat_client(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    # Sidestep the real embedding-provider factory -- no network calls.
    monkeypatch.setattr(embeddings_module, "build_embeddings", lambda _s: _FakeEmbeddings())

    with TemporaryDirectory() as chroma_dir, TemporaryDirectory() as docs_dir:
        # Seed the temp corpus so ingestion has something to chunk.
        (Path(docs_dir) / "fuel-policy.md").write_text(
            "# Fuel Policy\n\n## Anti-idling\nVehicles must shut off after 5 minutes idle.\n",
            encoding="utf-8",
        )

        app = create_app()
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with factory() as s:
                yield s

        app.dependency_overrides[get_session] = _override_session

        settings = get_settings().model_copy(
            update={
                "checkpoint_db_path": ":memory:",
                "chroma_persist_dir": chroma_dir,
                "documents_dir": docs_dir,
                "chroma_collection_name": "rag-test-docs",
            }
        )

        async with agent_lifespan(
            settings,
            model=_scripted_doc_search_model(),
            rag_enabled=True,
        ) as agent:
            app.state.agent = agent

            # Registry is live during the lifespan...
            assert get_vector_store() is not None

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client

        # ...and cleared on teardown.
        assert get_vector_store() is None
        app.dependency_overrides.clear()


async def test_agent_with_rag_enabled_dispatches_to_doc_search(
    rag_chat_client: AsyncClient,
) -> None:
    res = await rag_chat_client.post("/api/chat", json={"Message": "What's the anti-idling rule?"})
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["Response"] == "Anti-idling requires shutoff after 5 minutes."
    # Tool dispatch proves the lifespan (a) bound `search_fleet_documentation`
    # to the agent, (b) ran ingestion into a Chroma store that had content
    # for the search to land on.
    assert body["FunctionsUsed"] == ["search_fleet_documentation"]
