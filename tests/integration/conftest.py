"""Shared fixtures + scripted chat model for chat integration tests.

Both the sync (`/api/chat`) and streaming (`/api/chat/stream`) tests
want the same thing: a real FastAPI app wired to a real LangGraph
agent, but with the chat model swapped for a scripted fake so tests
don't need a live provider key. Defining the fixtures here keeps the
two test modules narrowly focused on their own assertions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fleetwise.ai.agent import agent_lifespan
from fleetwise.data.db import get_session
from fleetwise.main import create_app
from fleetwise.settings import get_settings


class ScriptedToolCallingModel(BaseChatModel):
    """Scripted fake that answers `.bind_tools` with `self`.

    `responses` is cycled once in order; after the final response the
    conditional edge in the graph sees an AIMessage with no `tool_calls`
    and terminates. Production graphs also see streamed deltas via
    `astream_events`; this fake doesn't bother streaming -- LangGraph
    synthesizes a single `on_chat_model_stream` event from the full
    `AIMessage` when the underlying model doesn't support streaming,
    which is what we want for the SSE integration test.
    """

    responses: list[BaseMessage]
    i: int = 0

    @property
    def _llm_type(self) -> str:  # pragma: no cover - trivial
        return "scripted-tool-calling-fake"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Runnable[Any, Any] | BaseTool],
        **kwargs: Any,
    ) -> Runnable[Any, BaseMessage]:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        response = self.responses[self.i]
        if self.i < len(self.responses) - 1:
            self.i += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async-stream the scripted AIMessage as a single chunk.

        LangGraph only emits `on_chat_model_stream` events when the
        model actually streams. Without this override the streaming
        integration test would see tool + done frames but no tokens.
        One chunk per scripted turn is enough -- the framer's
        delta-concatenation behavior is covered by unit tests.
        """
        response = self.responses[self.i]
        if self.i < len(self.responses) - 1:
            self.i += 1
        content = response.content if isinstance(response.content, str) else ""
        chunk = AIMessageChunk(
            content=content,
            tool_calls=getattr(response, "tool_calls", []) or [],
        )
        yield ChatGenerationChunk(message=chunk)


def scripted_fleet_summary_model() -> ScriptedToolCallingModel:
    """Two-turn script: call `get_fleet_summary`, then answer."""
    return ScriptedToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_fleet_summary",
                        "args": {},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="The fleet has 35 vehicles across several departments."),
        ]
    )


@pytest_asyncio.fixture
async def chat_app(engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    """App with a real agent graph but a scripted chat model.

    We don't use the default `app` fixture because its lifespan builds
    a live provider client. This fixture hand-builds the agent bundle
    with the scripted fake + an in-memory checkpointer, so tests stay
    hermetic.
    """
    app = create_app()

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session

    settings = get_settings()
    settings_copy = settings.model_copy(update={"checkpoint_db_path": ":memory:"})
    async with agent_lifespan(
        settings_copy,
        model=scripted_fleet_summary_model(),
        rag_enabled=False,  # keep this fixture hermetic; RAG has its own tests
    ) as agent:
        app.state.agent = agent
        yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def chat_client(chat_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
