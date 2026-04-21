"""Chat endpoints.

Two routes share the same agent + checkpointer and only differ in how
they deliver the assistant's reply:

- `POST /api/chat` -- one-shot, returns the full turn as JSON.
- `POST /api/chat/stream` -- SSE, emits `token` / `tool` frames as
  LangGraph produces them, followed by a terminal `done` frame.

`conversation_id` is LangGraph's `thread_id`: each conversation gets its
own partition in the `AsyncSqliteSaver` checkpointer, so follow-up turns
resume exactly where the last one left off even across process restarts.
The minted id is echoed back in the response body (sync path) and in the
`X-Conversation-Id` response header (stream path) so the frontend can
thread follow-ups the same way in both modes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from fleetwise.ai.agent import extract_functions_used, final_ai_text
from fleetwise.ai.sse import to_sse_frames
from fleetwise.api.deps import AgentDep
from fleetwise.domain.dto import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, agent: AgentDep) -> ChatResponse:
    """Run one ReAct turn and return the assistant's response.

    If the client omitted `ConversationId`, we mint a new one and return
    it so the caller can thread follow-ups through the same checkpointer
    partition. Matches the .NET controller's behavior.
    """
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}

    result = await agent.graph.ainvoke(
        {"messages": [HumanMessage(content=payload.message)]},
        config=config,
    )
    messages = result.get("messages", [])

    return ChatResponse(
        response=final_ai_text(messages),
        conversation_id=conversation_id,
        functions_used=extract_functions_used(messages),
    )


@router.post("/stream")
async def chat_stream(payload: ChatRequest, agent: AgentDep) -> StreamingResponse:
    """Stream one ReAct turn as SSE.

    LangGraph's `astream_events(version="v2")` yields a rich event feed;
    `to_sse_frames` projects it to the three wire events the frontend
    cares about (`token`, `tool`, `done`). The conversation id is echoed
    in `X-Conversation-Id` so the browser can thread follow-ups -- we
    can't stuff it in the body because the body is a live token stream.
    """
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}

    events = agent.graph.astream_events(
        {"messages": [HumanMessage(content=payload.message)]},
        config=config,
        version="v2",
    )
    return StreamingResponse(
        to_sse_frames(events),
        media_type="text/event-stream",
        headers={"X-Conversation-Id": conversation_id},
    )
