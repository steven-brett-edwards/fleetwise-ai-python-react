"""Unit tests for the hand-rolled StateGraph's conditional router.

The full agent loop is covered by the chat integration tests; here we
pin the one piece of custom logic in `agent.py` -- the `_should_continue`
edge that decides whether to call tools again or end the turn.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from fleetwise.ai.agent import _should_continue


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
