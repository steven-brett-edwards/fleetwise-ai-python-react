"""Work-order tools -- parity with `WorkOrderPlugin.cs`.

Three tools: open work orders, detail-by-number, and parts below
reorder threshold.
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from fleetwise.ai.tools._formatting import format_list, format_single
from fleetwise.ai.tools._session import tool_session
from fleetwise.data.repositories import part as part_repo, work_order as work_order_repo
from fleetwise.domain.entities import Part, WorkOrder


class _Empty(BaseModel):
    pass


class _WorkOrderNumberArgs(BaseModel):
    work_order_number: str = Field(
        ..., description="The work order number to look up (format: WO-YYYY-NNNNN)"
    )


def _work_order_summary_row(wo: WorkOrder) -> dict[str, object]:
    return {
        "WorkOrderNumber": wo.work_order_number,
        "AssetNumber": wo.vehicle.asset_number,
        "VehicleDescription": f"{wo.vehicle.year} {wo.vehicle.make} {wo.vehicle.model}",
        "Status": wo.status.value,
        "Priority": wo.priority.value,
        "Description": wo.description,
        "RequestedDate": wo.requested_date,
        "AssignedTechnician": wo.assigned_technician,
    }


def _work_order_detail_row(wo: WorkOrder) -> dict[str, object]:
    return {
        "WorkOrderNumber": wo.work_order_number,
        "AssetNumber": wo.vehicle.asset_number,
        "VehicleDescription": f"{wo.vehicle.year} {wo.vehicle.make} {wo.vehicle.model}",
        "Status": wo.status.value,
        "Priority": wo.priority.value,
        "Description": wo.description,
        "RequestedDate": wo.requested_date,
        "CompletedDate": wo.completed_date,
        "AssignedTechnician": wo.assigned_technician,
        "LaborHours": wo.labor_hours,
        "TotalCost": wo.total_cost,
        "Notes": wo.notes,
    }


def _part_row(p: Part) -> dict[str, object]:
    return {
        "PartNumber": p.part_number,
        "Name": p.name,
        "Category": p.category,
        "QuantityInStock": p.quantity_in_stock,
        "ReorderThreshold": p.reorder_threshold,
        "Deficit": p.reorder_threshold - p.quantity_in_stock,
        "UnitCost": p.unit_cost,
        "Location": p.location,
    }


@tool(
    "get_open_work_orders",
    args_schema=_Empty,
    description=(
        "Returns all open and in-progress work orders with their priority, assigned "
        "technician, and associated vehicle. Use this when the user asks about current "
        "work, open tickets, or what repairs are in progress."
    ),
)
async def get_open_work_orders() -> str:
    async with tool_session() as session:
        work_orders = await work_order_repo.get_open_work_orders(session)
    if not work_orders:
        return "No open work orders found."
    return format_list(
        f"Found {len(work_orders)} open work orders",
        [_work_order_summary_row(wo) for wo in work_orders],
    )


@tool(
    "get_work_order_details",
    args_schema=_WorkOrderNumberArgs,
    description=(
        "Returns full details of a specific work order by its work order number. Work "
        "order numbers follow the format WO-YYYY-NNNNN (e.g., WO-2026-00142)."
    ),
)
async def get_work_order_details(work_order_number: str) -> str:
    async with tool_session() as session:
        wo = await work_order_repo.get_by_work_order_number(session, work_order_number)
    if wo is None:
        return f"No work order found with number {work_order_number}."
    return format_single(
        f"Work order {wo.work_order_number}: {wo.description}",
        _work_order_detail_row(wo),
    )


@tool(
    "get_parts_below_reorder_threshold",
    args_schema=_Empty,
    description=(
        "Returns parts inventory items that are below their reorder threshold and need "
        "to be restocked. Use this when the user asks about low stock, parts inventory, "
        "or supply issues."
    ),
)
async def get_parts_below_reorder_threshold() -> str:
    async with tool_session() as session:
        parts = await part_repo.get_below_reorder_threshold(session)
    if not parts:
        return "All parts are above their reorder thresholds. No restocking needed."
    return format_list(
        f"Found {len(parts)} parts below reorder threshold",
        [_part_row(p) for p in parts],
    )


work_order_tools = [
    get_open_work_orders,
    get_work_order_details,
    get_parts_below_reorder_threshold,
]
