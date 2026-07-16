"""Unit tests for the hand-rolled StateGraph's conditional router.

The full agent loop is covered by the chat integration tests; here we
pin the one piece of custom logic in `agent.py` -- the `should_continue`
edge that decides whether to call tools again or end the turn.
"""

from __future__ import annotations

import aiosqlite
import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from fleetwise.ai import agent as agent_module
from fleetwise.ai.agent import (
    MAX_TURN_MESSAGES,
    agent_lifespan,
    build_graph,
    extract_functions_used,
    final_ai_text,
    last_turn_messages,
    should_continue,
    window_messages,
)
from fleetwise.ai.tools._retrieval import get_vector_store
from fleetwise.settings import Settings


def test_should_continue_routes_to_tools_when_ai_message_has_tool_calls() -> None:
    state = {
        "messages": [
            HumanMessage(content="hi"),
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
        ]
    }
    assert should_continue(state) == "tools"  # type: ignore[arg-type]


def test_should_continue_ends_when_last_ai_message_has_no_tool_calls() -> None:
    state = {
        "messages": [
            HumanMessage(content="hi"),
            AIMessage(content="The fleet has 35 vehicles."),
        ]
    }
    # `__end__` is the LangGraph terminal-node sentinel; `END` re-exports
    # that string but the edge signature is the literal.
    assert should_continue(state) == "__end__"  # type: ignore[arg-type]


def test_should_continue_ends_when_last_message_is_not_ai_message() -> None:
    # Defensive: if something odd is on the tail (e.g. a tool error
    # shaped as a HumanMessage in a test), don't loop -- terminate.
    state = {"messages": [HumanMessage(content="hi")]}
    assert should_continue(state) == "__end__"  # type: ignore[arg-type]


# --- agent_lifespan RAG decision + degrade paths ---------------------------
#
# `build_embeddings` is the single decision point (the old `_rag_available`
# pre-probe duplicated its logic and its `auto` branch had decayed into a
# constant True). These pin the lifespan-level contract: disabled configs
# boot without RAG, explicit misconfiguration is loud, and runtime setup
# failures degrade to a RAG-less agent instead of failing the boot.


def _s(**overrides: object) -> Settings:
    # Bypass env loading so these assertions stay hermetic.
    base = Settings.model_construct(
        embedding_provider="auto",
        openai_api_key=None,
        checkpoint_db_path=":memory:",
    )
    return base.model_copy(update=overrides)


def _fake_chat_model() -> RunnableLambda[object, AIMessage]:
    return RunnableLambda(lambda _msgs: AIMessage(content="ok"))


async def test_agent_lifespan_boots_without_rag_when_provider_disabled() -> None:
    async with agent_lifespan(_s(embedding_provider="disabled"), model=_fake_chat_model()) as b:
        assert b.graph is not None
        assert get_vector_store() is None


async def test_agent_lifespan_fails_loudly_for_explicit_openai_without_key() -> None:
    # Explicit provider + missing config is operator error; a silent
    # RAG-less boot would hide it (the old probe did exactly that).
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is unset"):
        async with agent_lifespan(_s(embedding_provider="openai"), model=_fake_chat_model()):
            pass  # pragma: no cover - lifespan raises before yielding


async def test_agent_lifespan_degrades_when_rag_setup_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Simulate `auto` falling back to an Ollama that isn't running: the
    # embedding factory succeeds, the store/ingest step blows up.
    monkeypatch.setattr(agent_module, "build_embeddings", lambda _s: object())

    def _boom(_embeddings: object, _settings: Settings) -> object:
        raise ConnectionError("connection refused: localhost:11434")

    monkeypatch.setattr(agent_module, "build_vector_store", _boom)

    with caplog.at_level("WARNING", logger="fleetwise.ai.agent"):
        async with agent_lifespan(_s(), model=_fake_chat_model(), rag_enabled=True) as b:
            assert b.graph is not None
            assert get_vector_store() is None

    assert "RAG setup failed" in caplog.text


async def test_agent_lifespan_rag_disabled_flag_never_touches_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _explode(_settings: Settings) -> object:
        raise AssertionError("build_embeddings must not be called with rag_enabled=False")

    monkeypatch.setattr(agent_module, "build_embeddings", _explode)

    async with agent_lifespan(_s(), model=_fake_chat_model(), rag_enabled=False) as b:
        assert b.graph is not None
        assert get_vector_store() is None


# --- final_ai_text / extract_functions_used ------------------------------


def test_final_ai_text_pulls_latest_non_empty_string_content() -> None:
    msgs = [
        AIMessage(content=""),  # tool-call-only turn, skipped
        AIMessage(content="Interim answer."),
        AIMessage(content="Final answer."),
    ]
    assert final_ai_text(msgs) == "Final answer."


def test_final_ai_text_concatenates_anthropic_content_blocks() -> None:
    # Anthropic returns a list of typed blocks; text blocks are joined
    # and non-text blocks are dropped.
    msg = AIMessage(
        content=[
            {"type": "text", "text": "Hello "},
            {"type": "tool_use", "name": "noise"},
            {"type": "text", "text": "there"},
        ]
    )
    assert final_ai_text([msg]) == "Hello there"


def test_extract_functions_used_dedupes_preserving_order() -> None:
    msgs = [
        ToolMessage(content="", name="get_fleet_summary", tool_call_id="1"),
        ToolMessage(content="", name="search_vehicles", tool_call_id="2"),
        ToolMessage(content="", name="get_fleet_summary", tool_call_id="3"),  # dup
    ]
    assert extract_functions_used(msgs) == ["get_fleet_summary", "search_vehicles"]


# --- last_turn_messages slicing --------------------------------------------


def test_last_turn_messages_slices_from_final_human_message() -> None:
    turn_one = [
        HumanMessage(content="How big is the fleet?"),
        AIMessage(content="", tool_calls=[{"name": "get_fleet_summary", "args": {}, "id": "1"}]),
        ToolMessage(content="35 vehicles", name="get_fleet_summary", tool_call_id="1"),
        AIMessage(content="35 vehicles."),
    ]
    turn_two = [
        HumanMessage(content="Thanks!"),
        AIMessage(content="You're welcome."),
    ]

    sliced = last_turn_messages([*turn_one, *turn_two])

    assert sliced == turn_two
    # The whole point: tool usage from turn 1 must not leak into turn 2.
    assert extract_functions_used(sliced) == []


def test_last_turn_messages_returns_everything_when_no_human_message() -> None:
    # Defensive fallback -- a thread always starts with a HumanMessage in
    # practice, but slicing must not explode on a weird message log.
    msgs = [AIMessage(content="orphan answer")]
    assert last_turn_messages(msgs) == msgs


# --- window_messages --------------------------------------------------------


def test_window_messages_passes_short_histories_through() -> None:
    msgs = [HumanMessage(content="hi"), AIMessage(content="hello")]
    assert window_messages(msgs) == msgs


def test_window_messages_keeps_only_the_newest_limit_messages() -> None:
    msgs = [HumanMessage(content=f"m{i}") for i in range(50)]
    windowed = window_messages(msgs, limit=40)
    assert len(windowed) == 40
    assert windowed[0].content == "m10"
    assert windowed[-1].content == "m49"


def test_window_messages_drops_orphaned_leading_tool_results() -> None:
    # If the cut lands between a tool-calls AIMessage and its results,
    # the leading ToolMessages must go -- providers reject a tool result
    # whose parent call is missing.
    msgs: list[BaseMessage] = [
        HumanMessage(content="old question"),
        AIMessage(content="", tool_calls=[{"name": "get_fleet_summary", "args": {}, "id": "1"}]),
        ToolMessage(content="35", name="get_fleet_summary", tool_call_id="1"),
        ToolMessage(content="12", name="search_vehicles", tool_call_id="2"),
        AIMessage(content="Answer."),
        HumanMessage(content="new question"),
    ]
    # limit=4 cuts inside the tool block: [Tool, Tool, AI, Human] -> [AI, Human]
    windowed = window_messages(msgs, limit=4)
    assert [type(m).__name__ for m in windowed] == ["AIMessage", "HumanMessage"]


def test_window_messages_survives_all_tool_history() -> None:
    msgs: list[BaseMessage] = [
        ToolMessage(content="35", name="get_fleet_summary", tool_call_id="1"),
    ]
    assert window_messages(msgs, limit=1) == []


async def test_agent_node_windows_history_and_prepends_system_prompt() -> None:
    # Graph-level check: a long thread reaches the LLM as (system prompt +
    # the newest MAX_TURN_MESSAGES), not the whole history.
    captured: list[list[BaseMessage]] = []

    def fake_llm(msgs: object) -> AIMessage:
        assert isinstance(msgs, list)
        captured.append(list(msgs))
        return AIMessage(content="ok")

    async with aiosqlite.connect(":memory:") as conn:
        graph = build_graph(
            RunnableLambda(fake_llm),
            checkpointer=AsyncSqliteSaver(conn),
            tools=[],
        )
        long_thread = [HumanMessage(content=f"m{i}") for i in range(60)]
        await graph.ainvoke(
            {"messages": long_thread},
            config={"configurable": {"thread_id": "window-test"}},
        )

    (llm_input,) = captured
    assert len(llm_input) == MAX_TURN_MESSAGES + 1  # window + system prompt
    assert isinstance(llm_input[0], SystemMessage)
    assert llm_input[1].content == "m20"
    assert llm_input[-1].content == "m59"
