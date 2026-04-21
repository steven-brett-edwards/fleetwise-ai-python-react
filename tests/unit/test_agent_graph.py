"""Unit tests for the hand-rolled StateGraph's conditional router.

The full agent loop is covered by the chat integration tests; here we
pin the one piece of custom logic in `agent.py` -- the `_should_continue`
edge that decides whether to call tools again or end the turn.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from fleetwise.ai.agent import (
    _rag_available,
    _should_continue,
    extract_functions_used,
    final_ai_text,
)
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
    assert _should_continue(state) == "tools"  # type: ignore[arg-type]


def test_should_continue_ends_when_last_ai_message_has_no_tool_calls() -> None:
    state = {
        "messages": [
            HumanMessage(content="hi"),
            AIMessage(content="The fleet has 35 vehicles."),
        ]
    }
    # `__end__` is the LangGraph terminal-node sentinel; `END` re-exports
    # that string but the edge signature is the literal.
    assert _should_continue(state) == "__end__"  # type: ignore[arg-type]


def test_should_continue_ends_when_last_message_is_not_ai_message() -> None:
    # Defensive: if something odd is on the tail (e.g. a tool error
    # shaped as a HumanMessage in a test), don't loop -- terminate.
    state = {"messages": [HumanMessage(content="hi")]}
    assert _should_continue(state) == "__end__"  # type: ignore[arg-type]


# --- _rag_available probe -------------------------------------------------


def _s(**overrides: object) -> Settings:
    # Bypass env loading so these assertions stay hermetic.
    base = Settings.model_construct(
        embedding_provider="auto",
        openai_api_key=None,
    )
    return base.model_copy(update=overrides)


def test_rag_available_false_when_disabled() -> None:
    assert _rag_available(_s(embedding_provider="disabled")) is False


def test_rag_available_true_for_explicit_ollama() -> None:
    # Ollama is local and keyless; we optimistically say "yes" and let
    # the first embed call fail loudly if the server isn't running.
    assert _rag_available(_s(embedding_provider="ollama")) is True


def test_rag_available_requires_key_for_explicit_openai() -> None:
    assert _rag_available(_s(embedding_provider="openai")) is False
    assert _rag_available(_s(embedding_provider="openai", openai_api_key="sk-x")) is True


def test_rag_available_auto_is_true_via_ollama_fallback() -> None:
    # No OpenAI key -> falls back to Ollama, which is assumed present.
    assert _rag_available(_s(embedding_provider="auto")) is True


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
