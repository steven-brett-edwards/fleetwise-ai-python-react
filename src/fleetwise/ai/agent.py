"""LangGraph agent wiring -- Phase 4's hand-rolled StateGraph path.

Phase 3 used `langgraph.prebuilt.create_react_agent` to de-risk the
tool-calling loop. Phase 4 replaces that with an explicit two-node
`StateGraph` so (a) the flow is readable as a diagram, not hidden
behind a helper, and (b) we can splice in the conditional documentation
stanza the .NET PR #14 lesson demands when RAG lands in Phase 5 -- never
advertise `search_fleet_documentation` to the LLM unless the tool is
actually bound.

Shape:

        START
          │
          ▼
    ┌──────────┐   no tool_calls   ┌─────┐
    │  agent   │──────────────────▶│ END │
    └──────────┘                   └─────┘
        ▲  │ has tool_calls
        │  ▼
    ┌──────────┐
    │  tools   │
    └──────────┘

`agent_node` is the LLM call (tools bound); `tool_node` is LangGraph's
prebuilt `ToolNode` which dispatches `AIMessage.tool_calls` to the
registered tools. The conditional edge inspects the last `AIMessage`;
loop until the LLM emits an answer without tool calls.

The checkpointer lives on the compiled graph, same as Phase 3, so
conversations still survive restarts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Literal

import aiosqlite
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from fleetwise.ai.embeddings import build_embeddings
from fleetwise.ai.prompts import BASE_SYSTEM_PROMPT, DOCUMENTATION_STANZA
from fleetwise.ai.providers import build_chat_model
from fleetwise.ai.rag.ingestion import ingest_if_empty
from fleetwise.ai.rag.vector_store import build_vector_store
from fleetwise.ai.tools import LIVE_DATA_TOOLS, document_search_tools
from fleetwise.ai.tools._retrieval import set_vector_store
from fleetwise.settings import Settings


@dataclass(frozen=True)
class AgentBundle:
    """Everything an HTTP handler needs to drive one chat turn.

    `graph` is the compiled LangGraph agent. `checkpointer` is kept on
    the bundle so the lifespan owns its shutdown (we exit the context
    manager on app teardown, which closes the underlying aiosqlite conn).
    """

    # `CompiledStateGraph` is generic; we don't constrain the state type
    # here -- `MessagesState` is the only schema we use, but the generic
    # parameter churns between LangGraph versions.
    graph: CompiledStateGraph  # type: ignore[type-arg]
    checkpointer: AsyncSqliteSaver


def _should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
    """Conditional edge: loop to tools if the LLM requested any, else end.

    LangGraph names the terminal sentinel `__end__`; `END` re-exports
    that constant, but the return-type annotation has to be the literal
    string for the graph compiler to accept the function as an edge.
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "__end__"


def build_graph(
    model: BaseChatModel | Runnable[object, BaseMessage],
    *,
    checkpointer: AsyncSqliteSaver,
    tools: list[BaseTool],
    system_prompt: str = BASE_SYSTEM_PROMPT,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Compile the two-node StateGraph with the given model + tools bound.

    `model` is accepted as either a raw `BaseChatModel` (we'll bind tools
    here) or a pre-bound runnable (tests can hand us a scripted fake
    whose `bind_tools` already returned `self`). `tools` and `system_prompt`
    are explicit parameters so `agent_lifespan` can splice in the RAG tool
    + documentation stanza only when the vector store is available --
    never advertise a tool the LLM can't actually dispatch to.
    """
    # `bind_tools` returns a narrower `Runnable` parameterized on the
    # provider's message-input union; widen to `Runnable[object, ...]`
    # so the ternary's two branches land on the same type.
    bound: Runnable[object, BaseMessage] = (
        model.bind_tools(tools)  # type: ignore[assignment]
        if isinstance(model, BaseChatModel)
        else model
    )

    async def agent_node(state: MessagesState) -> dict[str, list[BaseMessage]]:
        """LLM call. Prepend the system prompt if it's not already there.

        The system prompt is injected on the first turn only -- subsequent
        turns replay history from the checkpointer, which already carries
        the prior system message.
        """
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt), *messages]
        response = await bound.ainvoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(tools)

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        _should_continue,
        {"tools": "tools", "__end__": END},
    )
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)


@asynccontextmanager
async def agent_lifespan(
    settings: Settings,
    *,
    model: BaseChatModel | Runnable[object, BaseMessage] | None = None,
    rag_enabled: bool | None = None,
) -> AsyncIterator[AgentBundle]:
    """Own the checkpointer + graph + (optional) vector store for an app's lifetime.

    `model` is an override hook for tests -- pass a scripted fake to
    skip the live provider. `rag_enabled` forces RAG on/off for tests
    that want to pin the behavior regardless of environment; production
    callers leave it `None` and let `build_embeddings` probe the config.

    When RAG is active we (a) build the Chroma store and register it in
    the tool-module retrieval registry so `search_fleet_documentation`
    can find it, (b) run one-shot ingestion if the collection is empty,
    (c) bind the RAG tool + append `DOCUMENTATION_STANZA` to the prompt.
    When RAG is inactive, none of those happen -- the LLM sees exactly
    the same tool surface it did in Phase 3.
    """
    chat_model: BaseChatModel | Runnable[object, BaseMessage]
    chat_model = model if model is not None else build_chat_model(settings)

    async with AsyncExitStack() as stack:
        # aiosqlite.connect accepts a filesystem path; `:memory:` works too
        # (useful in tests that want an ephemeral checkpoint store).
        conn = await stack.enter_async_context(aiosqlite.connect(settings.checkpoint_db_path))
        checkpointer = AsyncSqliteSaver(conn)

        tools: list[BaseTool] = list(LIVE_DATA_TOOLS)
        system_prompt = BASE_SYSTEM_PROMPT

        # Decide whether RAG is on. If the caller forced it we honor that
        # even when embeddings come back None; production paths go through
        # the auto-probe and cleanly degrade when no embedding backend is
        # reachable.
        should_enable_rag = rag_enabled if rag_enabled is not None else _rag_available(settings)

        if should_enable_rag:
            embeddings = build_embeddings(settings)
            if embeddings is not None:
                vector_store = build_vector_store(embeddings, settings)
                await ingest_if_empty(vector_store, settings.documents_dir)
                set_vector_store(vector_store)
                # Tear the registry down on shutdown so tests starting a
                # fresh app don't inherit a stale store from a previous run.
                stack.push_async_callback(_clear_vector_store)
                tools = [*tools, *document_search_tools]
                system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{DOCUMENTATION_STANZA}"

        graph = build_graph(
            chat_model,
            checkpointer=checkpointer,
            tools=tools,
            system_prompt=system_prompt,
        )
        yield AgentBundle(graph=graph, checkpointer=checkpointer)


def _rag_available(settings: Settings) -> bool:
    """Cheap probe: would `build_embeddings` return a usable provider?

    We don't actually call the factory here because that would instantiate
    a live client; just check the same preconditions the factory checks.
    """
    provider = settings.embedding_provider
    if provider == "disabled":
        return False
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "ollama":
        return True  # no key to probe; let first embed() fail loudly if unreachable
    # `auto`: prefer openai, else ollama.
    return bool(settings.openai_api_key) or True


async def _clear_vector_store() -> None:
    """AsyncExitStack callback to reset the tool retrieval registry."""
    set_vector_store(None)


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
