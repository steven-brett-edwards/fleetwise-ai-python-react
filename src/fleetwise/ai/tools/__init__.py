"""Tool registry.

Tools are grouped by plugin area so the agent builder can pick subsets --
Phase 4's conditional RAG wiring wants to add `document_search_tools`
only when embeddings are available.
"""

from __future__ import annotations

from fleetwise.ai.tools.document_search import document_search_tools
from fleetwise.ai.tools.fleet_query import fleet_query_tools
from fleetwise.ai.tools.inspection import inspection_tools
from fleetwise.ai.tools.maintenance import maintenance_tools
from fleetwise.ai.tools.work_order import work_order_tools

# Live-data tools only. RAG is spliced in at build time by `agent_lifespan`
# -- see the PR #14 lesson from the .NET edition: never advertise a tool
# the agent won't actually be able to dispatch to.
LIVE_DATA_TOOLS = [
    *fleet_query_tools,
    *maintenance_tools,
    *work_order_tools,
    *inspection_tools,
]

# Convenience alias preserved for callers that don't care about RAG
# conditionality (e.g. tool-only unit tests). Equivalent to live-data
# + doc-search; the agent builder decides which list to bind.
ALL_TOOLS = [*LIVE_DATA_TOOLS, *document_search_tools]

__all__ = [
    "ALL_TOOLS",
    "LIVE_DATA_TOOLS",
    "document_search_tools",
    "fleet_query_tools",
    "inspection_tools",
    "maintenance_tools",
    "work_order_tools",
]
