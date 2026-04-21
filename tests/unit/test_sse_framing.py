"""Unit tests for the SSE framing adapter.

The adapter has two jobs (see `ai/sse.py`): escape chunks so newlines
don't break SSE framing, and flatten LangGraph's `astream_events` output
to the three wire events the browser handles. These tests exercise both
jobs in isolation -- no graph, no LLM, synthetic events only.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from fleetwise.ai.sse import (
    done_frame,
    error_frame,
    escape_chunk,
    to_sse_frames,
    token_frame,
    tool_frame,
)


class _FakeChunk:
    """Minimal stand-in for a LangChain streaming chunk.

    `on_chat_model_stream` events carry an `AIMessageChunk`; we only use
    `.content`, so a duck-typed object is enough.
    """

    def __init__(self, content: Any) -> None:
        self.content = content


async def _aiter(items: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for item in items:
        yield item


async def _collect(events: AsyncIterator[str]) -> list[str]:
    return [frame async for frame in events]


# --- escape_chunk ---------------------------------------------------------


def test_escape_chunk_escapes_backslash_before_newline() -> None:
    # Order matters: if \n were escaped first, a literal `\n` (two chars)
    # would round-trip through the reverse mapping as a newline.
    assert escape_chunk("a\\nb") == "a\\\\nb"


def test_escape_chunk_escapes_newlines_and_carriage_returns() -> None:
    assert escape_chunk("line1\nline2\r\nline3") == "line1\\nline2\\r\\nline3"


def test_escape_chunk_passthrough_for_plain_text() -> None:
    assert escape_chunk("hello world") == "hello world"


# --- single-frame helpers -------------------------------------------------


def test_token_frame_is_well_formed_sse() -> None:
    # Every SSE frame: `event: <name>\ndata: <payload>\n\n`.
    assert token_frame("hi") == "event: token\ndata: hi\n\n"


def test_token_frame_escapes_embedded_newlines() -> None:
    assert token_frame("a\nb") == "event: token\ndata: a\\nb\n\n"


def test_tool_frame_uses_raw_name() -> None:
    # Tool names are identifiers -- no escaping needed and we want them
    # intact on the wire.
    assert tool_frame("get_fleet_summary") == "event: tool\ndata: get_fleet_summary\n\n"


def test_error_frame_escapes_message() -> None:
    # Error messages often include multi-line stack snippets; escape them
    # so the client's line-split parser doesn't choke.
    assert error_frame("boom\nbadly") == "event: error\ndata: boom\\nbadly\n\n"


def test_done_frame_is_terminal_sentinel() -> None:
    assert done_frame() == "event: done\ndata: [DONE]\n\n"


# --- to_sse_frames projection --------------------------------------------


async def test_chat_model_stream_projects_to_token_frame() -> None:
    events = _aiter(
        [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk("hello ")},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk("world")},
            },
        ]
    )
    out = await _collect(to_sse_frames(events))

    assert out == [
        "event: token\ndata: hello \n\n",
        "event: token\ndata: world\n\n",
        "event: done\ndata: [DONE]\n\n",  # `finally` always terminates.
    ]


async def test_anthropic_content_blocks_are_concatenated() -> None:
    # Anthropic chunks carry a list of content blocks; we keep only the
    # text blocks and concatenate them. Non-text blocks (tool_use deltas
    # etc.) are intentionally dropped -- tool invocations get their own
    # frame via `on_tool_start`.
    chunk = _FakeChunk(
        [
            {"type": "text", "text": "Hello "},
            {"type": "tool_use", "name": "noise"},
            {"type": "text", "text": "there"},
        ]
    )
    events = _aiter([{"event": "on_chat_model_stream", "data": {"chunk": chunk}}])
    out = await _collect(to_sse_frames(events))

    assert out[0] == "event: token\ndata: Hello there\n\n"
    assert out[-1] == done_frame()


async def test_empty_chunk_content_is_skipped() -> None:
    # Providers sometimes emit empty-string deltas; surfacing them as
    # `token` frames wastes bytes on the wire.
    events = _aiter(
        [
            {"event": "on_chat_model_stream", "data": {"chunk": _FakeChunk("")}},
            {"event": "on_chat_model_stream", "data": {"chunk": _FakeChunk(None)}},
        ]
    )
    out = await _collect(to_sse_frames(events))

    assert out == [done_frame()]


async def test_tool_start_emits_tool_frame() -> None:
    events = _aiter(
        [
            {"event": "on_tool_start", "name": "get_fleet_summary"},
            {"event": "on_tool_start", "name": ""},  # should be dropped
        ]
    )
    out = await _collect(to_sse_frames(events))

    assert out == [
        "event: tool\ndata: get_fleet_summary\n\n",
        done_frame(),
    ]


async def test_unknown_event_types_are_ignored() -> None:
    # LangGraph emits many event kinds (`on_chain_start`, `on_chain_end`,
    # `on_llm_new_token`, ...). The adapter should simply skip anything
    # that isn't one of the three it cares about.
    events = _aiter(
        [
            {"event": "on_chain_start", "name": "agent"},
            {"event": "on_chain_end", "name": "agent"},
        ]
    )
    out = await _collect(to_sse_frames(events))

    assert out == [done_frame()]


async def test_exception_mid_stream_yields_error_frame_then_done() -> None:
    # Port of the .NET `SafeStreamChunksAsync` behavior: a mid-stream
    # crash should surface as an `error` frame, not a half-open response.
    async def boom() -> AsyncIterator[dict[str, Any]]:
        yield {"event": "on_chat_model_stream", "data": {"chunk": _FakeChunk("ok ")}}
        raise RuntimeError("kaboom")

    out = await _collect(to_sse_frames(boom()))

    assert out[0] == "event: token\ndata: ok \n\n"
    assert out[1].startswith("event: error\ndata: An error occurred: kaboom")
    assert out[-1] == done_frame()


async def test_cancelled_error_is_reraised() -> None:
    # Client disconnect is not an application error -- let uvicorn
    # clean up the task.
    async def cancel() -> AsyncIterator[dict[str, Any]]:
        yield {"event": "on_chat_model_stream", "data": {"chunk": _FakeChunk("x")}}
        raise asyncio.CancelledError()

    collected: list[str] = []
    with pytest.raises(asyncio.CancelledError):
        async for frame in to_sse_frames(cancel()):
            collected.append(frame)

    # We saw the token, the `finally` block got a chance to emit a
    # terminal `done` frame (best-effort -- the client may already be
    # gone), and crucially no `error` frame was written: cancellation
    # is not an application error.
    assert "event: token\ndata: x\n\n" in collected
    assert not any(f.startswith("event: error") for f in collected)
