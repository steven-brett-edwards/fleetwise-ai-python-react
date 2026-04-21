"""Integration test for `POST /api/chat/stream`.

Drives the whole pipeline end-to-end with a scripted chat model and
reads the raw response bytes off the wire to assert SSE framing. The
point isn't to re-test the framer (that's covered in
`tests/unit/test_sse_framing.py`) -- it's to prove the FastAPI route,
the StreamingResponse, and the LangGraph event feed are wired
together correctly.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("tool_session_factory")


async def test_stream_emits_token_tool_and_done_frames(
    chat_client: AsyncClient,
) -> None:
    # httpx's `.stream(...)` gives us the body chunks as they arrive.
    # The scripted model here is identical to the sync test's: one
    # tool call to `get_fleet_summary`, then a plaintext answer.
    body = b""
    async with chat_client.stream(
        "POST",
        "/api/chat/stream",
        json={"Message": "How big is the fleet?"},
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        # The conversation id is surfaced in a header so the frontend
        # can thread follow-ups (the body is a live token stream, so
        # we can't put it there).
        assert res.headers["x-conversation-id"]

        async for chunk in res.aiter_bytes():
            body += chunk

    text = body.decode("utf-8")

    # The token frame carries the assistant's answer. The scripted fake
    # doesn't stream deltas, so the whole answer arrives in one token
    # frame -- that's fine for the wiring assertion.
    assert "event: token\ndata: The fleet has 35 vehicles across several departments.\n\n" in text

    # The tool breadcrumb fires when LangGraph enters `get_fleet_summary`.
    assert "event: tool\ndata: get_fleet_summary\n\n" in text

    # The `finally` in `to_sse_frames` guarantees a terminal `done` frame.
    assert text.rstrip().endswith("event: done\ndata: [DONE]\n\n".rstrip())


async def test_stream_echoes_conversation_id_when_supplied(
    chat_client: AsyncClient,
) -> None:
    async with chat_client.stream(
        "POST",
        "/api/chat/stream",
        json={"Message": "ping", "ConversationId": "fixed-stream-thread"},
    ) as res:
        assert res.status_code == 200
        assert res.headers["x-conversation-id"] == "fixed-stream-thread"
        # Drain the body so the underlying response closes cleanly.
        async for _ in res.aiter_bytes():
            pass
