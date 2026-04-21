"""Integration tests for `POST /api/chat`.

The real LangGraph graph is wired up -- only the chat model is swapped
for a scripted fake that emits (a) a tool-call AIMessage, then (b) a
final text AIMessage. Hitting the endpoint exercises the full loop:
FastAPI → agent → tool → agent → response DTO.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fleetwise.ai.agent import agent_lifespan
from fleetwise.data.db import get_session
from fleetwise.main import create_app
from fleetwise.settings import get_settings


class _ScriptedToolCallingModel(BaseChatModel):
    """Scripted fake that supports `.bind_tools` (no-op) so `create_react_agent`
    can attach its tool list without demanding a real provider.

    `responses` is cycled once in order; after the last response the loop
    ends because `create_react_agent` checks for `tool_calls` on the last
    AIMessage -- supply a final message with no tool_calls to terminate.
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
        # The prebuilt agent calls this once at build time; we don't care
        # about the tool schema -- scripted responses already encode the
        # tool calls we want.
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


def _scripted_model() -> _ScriptedToolCallingModel:
    """Two-turn script: call `get_fleet_summary`, then answer."""
    return _ScriptedToolCallingModel(
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

    We don't use the default `app` fixture because its lifespan would
    try to build a live Anthropic client. Instead we hand-build the agent
    bundle with the scripted fake and install it on `app.state`.
    """
    app = create_app()

    # Override the session dependency so API routes (and the chat tools,
    # via the monkeypatched factory on the `tool_session_factory` fixture)
    # see the seeded in-memory DB.
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session

    # Swap in the scripted model + :memory: checkpointer so the lifespan
    # doesn't need an Anthropic key or a real filesystem path.
    settings = get_settings()
    settings_copy = settings.model_copy(update={"checkpoint_db_path": ":memory:"})
    async with agent_lifespan(settings_copy, model=_scripted_model()) as agent:
        app.state.agent = agent
        yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def chat_client(chat_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


pytestmark = pytest.mark.usefixtures("tool_session_factory")


async def test_chat_returns_response_conversation_id_and_functions_used(
    chat_client: AsyncClient,
) -> None:
    res = await chat_client.post("/api/chat", json={"Message": "How big is the fleet?"})
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["Response"] == "The fleet has 35 vehicles across several departments."
    assert isinstance(body["ConversationId"], str) and body["ConversationId"]
    assert body["FunctionsUsed"] == ["get_fleet_summary"]


async def test_chat_threads_follow_up_on_supplied_conversation_id(
    chat_client: AsyncClient,
) -> None:
    res = await chat_client.post(
        "/api/chat",
        json={"Message": "ping", "ConversationId": "fixed-thread-id"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ConversationId"] == "fixed-thread-id"
