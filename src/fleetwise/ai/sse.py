"""Server-Sent Events adapter for streaming chat turns.

Two jobs:

1. **Frame LangGraph's `astream_events` output as SSE.** LangGraph emits
   rich events (`on_chat_model_stream`, `on_tool_start`, ...); the browser
   only cares about text chunks and tool-call breadcrumbs, so we project
   and flatten before writing to the wire.

2. **Fix the .NET SSE framing bug in passing.** The .NET edition emits
   `data: {chunk}\\n\\n`. If `chunk` contains a literal `\\n`, the newline
   terminates the SSE event mid-chunk and the Angular line-split parser
   produces garbage. Escape `\\` and `\\n` in every chunk; the frontend
   reverses the escape before rendering. Two characters of overhead, one
   class of bugs closed.

Event types on the wire (`event:` line + `data:` payload):

- `token`  — a text delta from the LLM. `data` is the escaped chunk.
- `tool`   — a tool was invoked. `data` is the tool name.
- `error`  — mid-stream failure. `data` is the (escaped) error message.
- `done`   — stream terminator. `data` is `[DONE]`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


def escape_chunk(text: str) -> str:
    """Escape `\\` and newlines so a chunk is a single SSE `data:` line.

    Order matters: escape backslash first, then newlines -- otherwise a
    chunk containing literal `\\n` (the two characters) would round-trip
    through the reverse mapping as a newline.
    """
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _frame(event: str, data: str) -> str:
    """Assemble a single well-formed SSE event."""
    return f"event: {event}\ndata: {data}\n\n"


def token_frame(text: str) -> str:
    return _frame("token", escape_chunk(text))


def tool_frame(name: str) -> str:
    return _frame("tool", name)


def error_frame(message: str) -> str:
    return _frame("error", escape_chunk(message))


def done_frame() -> str:
    return _frame("done", "[DONE]")


def _extract_text(chunk: Any) -> str:
    """Pull plain text out of a LangChain streaming chunk.

    Anthropic / OpenAI / Ollama all use slightly different chunk shapes.
    `.content` is either a `str` or a list of content blocks (Anthropic);
    for the latter, concatenate any block whose `type == "text"`.
    Non-text blocks (tool-use deltas etc.) are intentionally dropped --
    tool invocations get their own `tool` SSE frame via `on_tool_start`.
    """
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


async def to_sse_frames(events: AsyncIterator[Any]) -> AsyncIterator[str]:
    """Map LangGraph `astream_events(version="v2")` → SSE frames.

    Only three event types carry user-visible payload:

    - `on_chat_model_stream`: incremental LLM output → `token` frame.
    - `on_tool_start`: breadcrumb so the frontend can show a "calling
      get_overdue_maintenance..." indicator → `tool` frame.
    - `on_chain_end` on the top-level graph: nothing to emit, but it
      lets us know the turn is done so we can close with `done`.

    Any exception inside the inner stream is converted to an `error`
    frame and the stream is closed cleanly -- never leave the client
    hanging on a half-open response. `asyncio.CancelledError` is re-raised
    (client disconnect is not an application error).
    """
    try:
        async for event in events:
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                text = _extract_text(chunk) if chunk is not None else ""
                if text:
                    yield token_frame(text)
            elif kind == "on_tool_start":
                name = event.get("name")
                if isinstance(name, str) and name:
                    yield tool_frame(name)
    except asyncio.CancelledError:
        # Client hung up. Don't swallow -- let uvicorn clean up the task.
        raise
    except Exception as exc:
        logger.exception("Stream error while framing SSE events")
        yield error_frame(f"An error occurred: {exc}")
    finally:
        yield done_frame()
