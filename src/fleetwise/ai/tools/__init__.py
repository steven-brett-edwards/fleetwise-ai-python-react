"""Tool registry.

Tools are grouped by plugin area so the agent builder can pick subsets --
Phase 4's conditional RAG wiring wants to add `document_search_tools`
only when embeddings are available.
"""

from __future__ import annotations

from fleetwise.ai.tools.fleet_query import fleet_query_tools
from fleetwise.ai.tools.maintenance import maintenance_tools
from fleetwise.ai.tools.work_order import work_order_tools

ALL_TOOLS = [*fleet_query_tools, *maintenance_tools, *work_order_tools]

__all__ = [
    "ALL_TOOLS",
    "fleet_query_tools",
    "maintenance_tools",
    "work_order_tools",
]
