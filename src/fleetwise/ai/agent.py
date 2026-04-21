"""LangGraph agent wiring -- Phase 3's prebuilt ReAct path.

The agent is built once per app lifecycle and stashed on `app.state` by
the lifespan hook. Requests reuse it and scope their turn to a
`thread_id` (the chat's `conversation_id`) so the `AsyncSqliteSaver`
checkpointer partitions history per conversation and survives restarts --
the free upgrade over the .NET `ConcurrentDictionary<string, ChatHistory>`
flagged in the migration plan.

Phase 4 will replace `create_react_agent` with a hand-rolled `StateGraph`
that branches on `settings.rag_enabled` for the documentation stanza.
Until then this is the shortest path to a working tool-calling loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

import aiosqlite
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from fleetwise.ai.prompts import BASE_SYSTEM_PROMPT
from fleetwise.ai.providers import build_chat_model
from fleetwise.ai.tools import ALL_TOOLS
from fleetwise.settings import Settings


@dataclass(frozen=True)
class AgentBundle:
    """Everything an HTTP handler needs to drive one chat turn.

    `graph` is the compiled LangGraph agent. `checkpointer` is kept on
    the bundle so the lifespan owns its shutdown (we exit the context
    manager on app teardown, which closes the underlying aiosqlite conn).
    """

    # `CompiledStateGraph` is generic; we don't constrain the state type
    # here since we're using the prebuilt ReAct schema in Phase 3.
    graph: CompiledStateGraph  # type: ignore[type-arg]
    checkpointer: AsyncSqliteSaver


@asynccontextmanager
async def agent_lifespan(
    settings: Settings,
    *,
    model: BaseChatModel | None = None,
) -> AsyncIterator[AgentBundle]:
    """Own the checkpointer + graph for an app's lifetime.

    `model` is an override hook for tests -- pass a `FakeListChatModel`
    to skip the live provider. Production callers leave it `None` and
    the provider factory reads `settings.ai_provider`.
    """
    chat_model = model if model is not None else build_chat_model(settings)
    async with AsyncExitStack() as stack:
        # aiosqlite.connect accepts a filesystem path; `:memory:` works too
        # (useful in tests that want an ephemeral checkpoint store).
        conn = await stack.enter_async_context(aiosqlite.connect(settings.checkpoint_db_path))
        checkpointer = AsyncSqliteSaver(conn)
        graph = create_react_agent(
            chat_model,
            tools=ALL_TOOLS,
            checkpointer=checkpointer,
            prompt=BASE_SYSTEM_PROMPT,
        )
        yield AgentBundle(graph=graph, checkpointer=checkpointer)


def extract_functions_used(messages: Iterable[BaseMessage]) -> list[str]:
    """Unique tool names in order of first call.

    Mirrors the .NET `FunctionsUsed` list on `ChatResponse`. `ToolMessage`
    instances carry the name of the tool whose result they hold; scanning
    the final message log in-order is the cheapest way to reconstruct the
    sequence the LLM chose. Dedupe-while-preserving-order because the
    .NET side emits one entry per unique function, not per call.
    """
    seen: dict[str, None] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.name and msg.name not in seen:
            seen[msg.name] = None
    return list(seen)


def final_ai_text(messages: Iterable[BaseMessage]) -> str:
    """Best-effort extraction of the final assistant reply.

    LangGraph returns the full message trace; the last `AIMessage` with
    non-empty string content is the user-facing answer. Tool-call-only
    `AIMessage`s (content=='' or a list of content blocks with no text)
    are skipped.
    """
    last_text = ""
    for msg in messages:
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str) and content.strip():
                last_text = content
            elif isinstance(content, list):
                # Anthropic returns structured content blocks; concatenate any
                # text blocks so we don't lose the answer when tool-calls +
                # text share a message.
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                joined = "".join(parts).strip()
                if joined:
                    last_text = joined
    return last_text
