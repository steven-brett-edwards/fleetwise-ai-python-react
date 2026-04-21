"""Chat endpoints -- Phase 3 ships the sync `POST /api/chat` turn.

`conversation_id` is LangGraph's `thread_id`: each conversation gets its
own partition in the `AsyncSqliteSaver` checkpointer, so follow-up turns
resume exactly where the last one left off even across process restarts.

Streaming (`POST /api/chat/stream`) lands in Phase 4 along with the
hand-rolled `StateGraph` and the SSE framing fix.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from fleetwise.ai.agent import extract_functions_used, final_ai_text
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
