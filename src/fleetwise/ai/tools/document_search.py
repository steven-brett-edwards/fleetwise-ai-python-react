"""Documentation-search tool -- parity with `DocumentSearchPlugin.cs`.

One tool: `search_fleet_documentation`. Only bound on the agent when
the RAG pipeline is actually wired up (see `agent_lifespan`) so the
LLM never sees a dangling tool description for a search path that
doesn't exist -- the PR #14 lesson from the .NET edition.

The description text is lifted verbatim from the .NET `[Description]`
attribute, including the `Do NOT use this for ...` anti-pattern block.
Those directives shape the tool-choice loop and shouldn't be paraphrased.
"""

from __future__ import annotations

import asyncio
from io import StringIO

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from fleetwise.ai.tools._retrieval import get_vector_store


class _SearchDocsArgs(BaseModel):
    query: str = Field(..., description="The search query describing what information you need")
    top_k: int = Field(3, description="Number of results to return (default 3)")


@tool(
    "search_fleet_documentation",
    args_schema=_SearchDocsArgs,
    description=(
        "Search fleet management documentation for policies, procedures, and guidelines. "
        "Use this for questions about: maintenance procedures, safety policies, work order "
        "SOPs, vehicle lifecycle and replacement criteria, fuel management and anti-idling "
        "policies, PPE requirements, accident reporting, parts ordering thresholds, and "
        "compliance guidelines. Do NOT use this for questions about specific vehicles, work "
        "orders, or live fleet data -- use the other fleet query functions for those."
    ),
)
async def search_fleet_documentation(query: str, top_k: int = 3) -> str:
    """Run a similarity search against the persistent Chroma collection.

    Returns the same banner + `--- Source: X (relevance: Y) ---` shape the
    .NET edition emits, so demo transcripts read the same across stacks.
    When the collection is unavailable (RAG disabled) the tool returns a
    plain-language notice rather than raising -- the LLM handles that
    more gracefully than a stack trace.
    """
    store = get_vector_store()
    if store is None:
        return (
            "Fleet documentation search is not available in this deployment. "
            "Answer from live fleet data or general knowledge instead."
        )

    # `similarity_search_with_relevance_scores` returns (doc, score) pairs
    # where score is a 0..1 relevance (higher = closer). The sync client
    # is fine for our scale; offload to a worker thread to keep the event
    # loop clear while the HTTP embedding call is in-flight.
    results = await asyncio.to_thread(store.similarity_search_with_relevance_scores, query, top_k)

    if not results:
        return (
            f'No documentation found matching: "{query}". '
            "Try rephrasing the query or ask about a specific policy area."
        )

    buf = StringIO()
    buf.write(f'Found the following relevant documentation for: "{query}"\n\n')
    for doc, score in results:
        source = doc.metadata.get("source", "unknown")
        buf.write(f"--- Source: {source} (relevance: {score:.3f}) ---\n")
        buf.write(f"{doc.page_content}\n\n")

    return buf.getvalue()


document_search_tools = [search_fleet_documentation]
