"""Maintenance tools -- parity with `MaintenancePlugin.cs`.

Five tools: overdue, upcoming, history-by-id, history-by-asset-number,
and cost summary.
"""

from __future__ import annotations

from dataclasses import asdict

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from fleetwise.ai.tools._formatting import format_list
from fleetwise.ai.tools._session import tool_session
from fleetwise.data.repositories import maintenance as maintenance_repo, vehicle as vehicle_repo
from fleetwise.domain.entities import MaintenanceRecord, MaintenanceSchedule

_VALID_GROUP_BYS = ("vehicle", "type", "month")


class _Empty(BaseModel):
    pass


class _UpcomingArgs(BaseModel):
    within_days: int = Field(30, description="Number of days to look ahead (default: 30)")
    within_miles: int = Field(5000, description="Mileage threshold to look ahead (default: 5000)")


class _VehicleIdArgs(BaseModel):
    vehicle_id: int = Field(..., description="The vehicle's database ID (integer)")


class _AssetNumberArgs(BaseModel):
    asset_number: str = Field(..., description="The vehicle's asset number (format: V-YYYY-NNNN)")


class _GroupByArgs(BaseModel):
    group_by: str = Field(
        "vehicle", description="How to group costs: 'vehicle', 'type', or 'month'"
    )


def _schedule_row(s: MaintenanceSchedule, *, include_last_completed: bool) -> dict[str, object]:
    row: dict[str, object] = {
        "AssetNumber": s.vehicle.asset_number,
        "VehicleDescription": f"{s.vehicle.year} {s.vehicle.make} {s.vehicle.model}",
        "MaintenanceType": s.maintenance_type.value,
        "NextDueDate": s.next_due_date,
        "NextDueMileage": s.next_due_mileage,
        "CurrentMileage": s.vehicle.current_mileage,
    }
    if include_last_completed:
        row["LastCompletedDate"] = s.last_completed_date
    return row


def _record_row(r: MaintenanceRecord) -> dict[str, object]:
    return {
        "MaintenanceType": r.maintenance_type.value,
        "PerformedDate": r.performed_date,
        "MileageAtService": r.mileage_at_service,
        "Description": r.description,
        "Cost": r.cost,
        "TechnicianName": r.technician_name,
    }


@tool(
    "get_overdue_maintenance",
    args_schema=_Empty,
    description=(
        "Returns all maintenance schedules that are past their due date or due mileage. "
        "Use this when the user asks about overdue maintenance, missed services, or "
        "vehicles needing immediate attention."
    ),
)
async def get_overdue_maintenance() -> str:
    async with tool_session() as session:
        schedules = await maintenance_repo.get_overdue_schedules(session)
    if not schedules:
        return "No overdue maintenance schedules found."
    return format_list(
        f"Found {len(schedules)} overdue maintenance schedules",
        [_schedule_row(s, include_last_completed=True) for s in schedules],
    )


@tool(
    "get_upcoming_maintenance",
    args_schema=_UpcomingArgs,
    description=(
        "Returns maintenance schedules coming due soon. Filters by days until due and "
        "miles until due. Use this to plan ahead or check what maintenance is needed soon."
    ),
)
async def get_upcoming_maintenance(within_days: int = 30, within_miles: int = 5000) -> str:
    async with tool_session() as session:
        schedules = await maintenance_repo.get_upcoming_schedules(
            session, within_days=within_days, within_miles=within_miles
        )
    if not schedules:
        return (
            f"No maintenance scheduled within the next {within_days} days or {within_miles} miles."
        )
    return format_list(
        f"Found {len(schedules)} upcoming maintenance schedules",
        [_schedule_row(s, include_last_completed=False) for s in schedules],
    )


@tool(
    "get_vehicle_maintenance_history",
    args_schema=_VehicleIdArgs,
    description=(
        "Returns the maintenance history for a specific vehicle by its database ID. Prefer "
        "get_maintenance_history_by_asset_number when the user references a vehicle by its "
        "asset number (e.g. 'V-2019-0042') -- this function is for the internal integer ID "
        "only."
    ),
)
async def get_vehicle_maintenance_history(vehicle_id: int) -> str:
    async with tool_session() as session:
        records = await maintenance_repo.get_by_vehicle_id(session, vehicle_id=vehicle_id)
    if not records:
        return f"No maintenance records found for vehicle ID {vehicle_id}."
    return format_list(
        f"Found {len(records)} maintenance records for vehicle ID {vehicle_id}",
        [_record_row(r) for r in records],
    )


@tool(
    "get_maintenance_history_by_asset_number",
    args_schema=_AssetNumberArgs,
    description=(
        "Returns the maintenance history for a specific vehicle by its asset number (e.g. "
        "'V-2019-0042'). Prefer this over get_vehicle_maintenance_history when the user "
        "references a vehicle by asset number -- it avoids the separate ID lookup step."
    ),
)
async def get_maintenance_history_by_asset_number(asset_number: str) -> str:
    async with tool_session() as session:
        vehicle = await vehicle_repo.get_by_asset_number(session, asset_number)
        if vehicle is None:
            return f"No vehicle found with asset number {asset_number}."
        records = await maintenance_repo.get_by_vehicle_id(session, vehicle_id=vehicle.id)
    if not records:
        return f"No maintenance records found for vehicle {asset_number}."
    return format_list(
        f"Found {len(records)} maintenance records for vehicle {asset_number}",
        [_record_row(r) for r in records],
    )


@tool(
    "get_maintenance_cost_summary",
    args_schema=_GroupByArgs,
    description=(
        "Returns a summary of maintenance costs grouped by a specified category. Valid "
        "groupBy values: 'vehicle' (costs per vehicle), 'type' (costs per maintenance type), "
        "'month' (costs per month)."
    ),
)
async def get_maintenance_cost_summary(group_by: str = "vehicle") -> str:
    if group_by.lower() not in _VALID_GROUP_BYS:
        return f"Invalid groupBy value '{group_by}'. Valid values: {', '.join(_VALID_GROUP_BYS)}"
    async with tool_session() as session:
        groups = await maintenance_repo.get_cost_summary(session, group_by=group_by.lower())
    if not groups:
        return "No maintenance cost data available."
    return format_list(
        f"Maintenance costs grouped by {group_by.lower()} ({len(groups)} groups)",
        [asdict(g) for g in groups],
    )


maintenance_tools = [
    get_overdue_maintenance,
    get_upcoming_maintenance,
    get_vehicle_maintenance_history,
    get_maintenance_history_by_asset_number,
    get_maintenance_cost_summary,
]
