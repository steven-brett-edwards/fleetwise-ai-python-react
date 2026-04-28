"""Inspection tool -- exposes ETL-loaded inspection records to the agent.

Single tool: ``get_recent_inspections(asset_number, limit=5)``. Description
deliberately specific so the LLM doesn't reach for it on maintenance /
work-order questions; those have their own tools that read from the
seeded relational data, not the ETL-loaded inspection table.
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from fleetwise.ai.tools._formatting import format_list
from fleetwise.ai.tools._session import tool_session
from fleetwise.data.repositories import inspection as inspection_repo
from fleetwise.domain.entities import VehicleInspection


class _GetRecentInspectionsArgs(BaseModel):
    asset_number: str = Field(
        ...,
        description="The vehicle's asset number (format: V-YYYY-NNNN)",
    )
    limit: int = Field(
        5,
        description="Maximum number of inspection records to return (default: 5)",
    )


def _row(i: VehicleInspection) -> dict[str, object]:
    return {
        "InspectedAt": i.inspected_at,
        "InspectorName": i.inspector_name,
        "Mileage": i.mileage,
        "Passed": i.passed,
        "Findings": i.findings,
        "Recommendations": i.recommendations,
        "SourceFile": i.source_file,
        "Orphan": i.vehicle_id is None,
    }


@tool("get_recent_inspections", args_schema=_GetRecentInspectionsArgs)
async def get_recent_inspections(asset_number: str, limit: int = 5) -> str:
    """Get recent vehicle inspection findings ingested via the ETL pipeline.

    Use this for questions about INSPECTIONS specifically -- "show me the
    latest inspection findings for V-2020-0015", "what did the last
    inspection on the backhoe turn up", "any failed inspections this
    quarter". Inspection records contain free-text findings and a pass/fail
    outcome; they're a separate data source from maintenance history and
    work orders.

    Do NOT use this for:
    - "is this vehicle overdue for maintenance" -> use get_overdue_maintenance.
    - "what work orders are open on this vehicle" -> use get_open_work_orders.
    - "what was the last service performed" -> use
      get_maintenance_history_by_asset_number.

    Returns up to `limit` records, newest first. Surfaces orphan rows
    (asset numbers loaded by ETL that don't match a seeded vehicle) with
    an `Orphan: true` flag so the model can call out the data-quality
    note in its response.
    """
    async with tool_session() as session:
        rows = await inspection_repo.get_recent_for_asset_number(
            session, asset_number=asset_number, limit=limit
        )
    if not rows:
        return f"No inspections found for asset number {asset_number}."
    return format_list(
        f"Found {len(rows)} inspection(s) for {asset_number}:",
        [_row(r) for r in rows],
    )


inspection_tools = [get_recent_inspections]
