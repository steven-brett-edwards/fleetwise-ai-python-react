"""Fleet-query tools -- parity with `FleetQueryPlugin.cs`.

Four tools: summary, asset-number lookup, filtered search, top-N by
maintenance cost. Function names, parameter names, and descriptions are
lifted verbatim from the .NET `[Description]` attributes -- those strings
are the LLM's only guidance for choosing a tool, so we don't paraphrase.
"""

from __future__ import annotations

from dataclasses import asdict

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from fleetwise.ai.tools._formatting import format_list, format_single
from fleetwise.ai.tools._session import tool_session
from fleetwise.data.repositories import vehicle as vehicle_repo
from fleetwise.domain.entities import Vehicle
from fleetwise.domain.enums import FuelType, VehicleStatus

_STATUS_VALUES = ", ".join(s.value for s in VehicleStatus)
_FUEL_VALUES = ", ".join(f.value for f in FuelType)


class _Empty(BaseModel):
    """Arg schema for zero-arg tools (LangChain requires an explicit schema)."""


class _AssetNumberArgs(BaseModel):
    asset_number: str = Field(..., description="The asset number to look up (format: V-YYYY-NNNN)")


class _SearchArgs(BaseModel):
    make: str | None = Field(None, description="Filter by make (e.g., Ford, Chevrolet)")
    model: str | None = Field(None, description="Filter by model (e.g., F-150, Silverado)")
    department: str | None = Field(
        None, description="Filter by department (e.g., Public Works, Parks and Recreation)"
    )
    status: str | None = Field(None, description=f"Filter by status: {_STATUS_VALUES}")
    fuel_type: str | None = Field(None, description=f"Filter by fuel type: {_FUEL_VALUES}")


class _TopNArgs(BaseModel):
    top_n: int = Field(10, description="Number of vehicles to return (default: 10)")


def _vehicle_summary_row(v: Vehicle) -> dict[str, object]:
    # Narrow projection matching the .NET anonymous object in SearchVehicles.
    return {
        "AssetNumber": v.asset_number,
        "Year": v.year,
        "Make": v.make,
        "Model": v.model,
        "FuelType": v.fuel_type.value,
        "Status": v.status.value,
        "Department": v.department,
        "CurrentMileage": v.current_mileage,
    }


def _vehicle_detail_row(v: Vehicle) -> dict[str, object]:
    return {
        "Id": v.id,
        "AssetNumber": v.asset_number,
        "VIN": v.vin,
        "Year": v.year,
        "Make": v.make,
        "Model": v.model,
        "FuelType": v.fuel_type.value,
        "Status": v.status.value,
        "Department": v.department,
        "AssignedDriver": v.assigned_driver,
        "CurrentMileage": v.current_mileage,
        "AcquisitionDate": v.acquisition_date,
        "AcquisitionCost": v.acquisition_cost,
        "LicensePlate": v.license_plate,
        "Location": v.location,
        "Notes": v.notes,
    }


@tool(
    "get_fleet_summary",
    args_schema=_Empty,
    description=(
        "Returns a summary of the fleet including total vehicle count and breakdowns by "
        "status, fuel type, and department. Use this when the user asks about fleet size, "
        "composition, or general fleet statistics."
    ),
)
async def get_fleet_summary() -> str:
    async with tool_session() as session:
        summary = await vehicle_repo.get_fleet_summary(session)
    return format_single(
        f"Fleet summary: {summary.total_vehicles} total vehicles",
        {
            "TotalVehicles": summary.total_vehicles,
            "ByStatus": summary.by_status,
            "ByFuelType": summary.by_fuel_type,
            "ByDepartment": summary.by_department,
        },
    )


@tool(
    "get_vehicle_by_asset_number",
    args_schema=_AssetNumberArgs,
    description=(
        "Looks up a specific vehicle by its asset number. Asset numbers follow the format "
        "V-YYYY-NNNN (e.g., V-2019-0042). Use this when the user references a specific "
        "vehicle."
    ),
)
async def get_vehicle_by_asset_number(asset_number: str) -> str:
    async with tool_session() as session:
        vehicle = await vehicle_repo.get_by_asset_number(session, asset_number)
    if vehicle is None:
        return f"No vehicle found with asset number {asset_number}."
    return format_single(
        f"Vehicle {vehicle.asset_number}: {vehicle.year} {vehicle.make} {vehicle.model}",
        _vehicle_detail_row(vehicle),
    )


def _parse_enum[T: VehicleStatus | FuelType](
    value: str | None, cls: type[T], valid: str
) -> T | None | str:
    """Return the enum value, `None`, or an error string to surface to the LLM."""
    if value is None:
        return None
    for member in cls:
        if member.value.lower() == value.lower():
            return member
    return f"Invalid value '{value}'. Valid values: {valid}"


@tool(
    "search_vehicles",
    args_schema=_SearchArgs,
    description=(
        "Search vehicles by make, model, department, status (Active, InShop, OutOfService, "
        "Retired), or fuel type (Gasoline, Diesel, Electric, Hybrid, CNG). All filters are "
        "optional -- combine them to narrow results."
    ),
)
async def search_vehicles(
    make: str | None = None,
    model: str | None = None,
    department: str | None = None,
    status: str | None = None,
    fuel_type: str | None = None,
) -> str:
    parsed_status = _parse_enum(status, VehicleStatus, _STATUS_VALUES)
    if isinstance(parsed_status, str):
        return parsed_status
    parsed_fuel = _parse_enum(fuel_type, FuelType, _FUEL_VALUES)
    if isinstance(parsed_fuel, str):
        return parsed_fuel

    async with tool_session() as session:
        vehicles = await vehicle_repo.search(
            session,
            make=make,
            model=model,
            department=department,
            status=parsed_status,
            fuel_type=parsed_fuel,
        )

    if not vehicles:
        return "No vehicles found matching the specified criteria."

    return format_list(
        f"Found {len(vehicles)} vehicles matching criteria",
        [_vehicle_summary_row(v) for v in vehicles],
    )


@tool(
    "get_vehicles_by_high_maintenance_cost",
    args_schema=_TopNArgs,
    description=(
        "Returns the vehicles with the highest total maintenance costs, ranked from most "
        "to least expensive. Use this when the user asks about costly vehicles, maintenance "
        "spending, or which vehicles cost the most to maintain."
    ),
)
async def get_vehicles_by_high_maintenance_cost(top_n: int = 10) -> str:
    async with tool_session() as session:
        rows = await vehicle_repo.get_vehicles_by_maintenance_cost(session, top_n=top_n)
    if not rows:
        return "No maintenance cost data available."
    return format_list(
        f"Top {len(rows)} vehicles by maintenance cost",
        [asdict(r) for r in rows],
    )


fleet_query_tools = [
    get_fleet_summary,
    get_vehicle_by_asset_number,
    search_vehicles,
    get_vehicles_by_high_maintenance_cost,
]
