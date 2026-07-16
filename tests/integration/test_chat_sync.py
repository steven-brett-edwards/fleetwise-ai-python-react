"""Integration tests for `POST /api/chat`.

The real LangGraph graph is wired up -- only the chat model is swapped
for a scripted fake via the `chat_client` fixture (see conftest).
Hitting the endpoint exercises the full loop: FastAPI → agent →
tool → agent → response DTO.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

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


async def test_chat_functions_used_reports_current_turn_only(
    chat_client: AsyncClient,
) -> None:
    """Regression: FunctionsUsed must not accumulate across turns.

    The checkpointer makes `ainvoke` return the whole thread, so scanning
    it naively re-reports turn 1's tools on every later turn (the .NET
    edition's PR #20 bug, faithfully ported). The scripted model calls
    `get_fleet_summary` on turn 1 and answers turn 2 with plain text
    (it replays its final response once the script is exhausted), so
    turn 2 must report an empty FunctionsUsed list.
    """
    thread = {"ConversationId": "functions-per-turn-thread"}

    first = await chat_client.post("/api/chat", json={"Message": "How big is the fleet?", **thread})
    assert first.status_code == 200, first.text
    assert first.json()["FunctionsUsed"] == ["get_fleet_summary"]

    second = await chat_client.post("/api/chat", json={"Message": "Thanks!", **thread})
    assert second.status_code == 200, second.text
    assert second.json()["FunctionsUsed"] == []


async def test_chat_rejects_oversized_message(chat_client: AsyncClient) -> None:
    # The DTO caps Message at 2000 chars so one request can't carry an
    # outsized prompt to the paid LLM API. FastAPI rejects before the
    # agent ever runs.
    res = await chat_client.post("/api/chat", json={"Message": "x" * 2001})
    assert res.status_code == 422


async def test_chat_rejects_empty_message(chat_client: AsyncClient) -> None:
    res = await chat_client.post("/api/chat", json={"Message": ""})
    assert res.status_code == 422


async def test_chat_requests_over_rate_limit_get_429(chat_client: AsyncClient) -> None:
    """The middleware is wired into the real app (default: 15/min per IP).

    The per-app counter starts fresh for this test's app instance, so
    requests 1-15 pass and 16 trips the limit.
    """
    for i in range(15):
        res = await chat_client.post("/api/chat", json={"Message": f"ping {i}"})
        assert res.status_code == 200, f"request {i + 1}: {res.text}"

    res = await chat_client.post("/api/chat", json={"Message": "one too many"})
    assert res.status_code == 429
    assert res.headers["retry-after"] == "60"
