"""Tool-layer tests for `ai.tools.fleet_query`.

Every test invokes the tool via `.ainvoke({...})` -- the same path
LangGraph uses at runtime. The `tool_session_factory` fixture swaps the
module-level session factory to the per-test in-memory engine, so each
tool call hits the seeded fleet.
"""

from __future__ import annotations

import pytest

from fleetwise.ai.tools.fleet_query import (
    get_fleet_summary,
    get_vehicle_by_asset_number,
    get_vehicles_by_high_maintenance_cost,
    search_vehicles,
)

pytestmark = pytest.mark.usefixtures("tool_session_factory")


async def test_get_fleet_summary_emits_totals_and_breakdowns() -> None:
    out = await get_fleet_summary.ainvoke({})
    # Preface carries the "Fleet summary: N total vehicles" shape from the .NET plugin.
    assert "Fleet summary: 35 total vehicles" in out
    assert '"TotalVehicles": 35' in out
    assert '"ByStatus"' in out
    assert '"ByFuelType"' in out
    assert '"ByDepartment"' in out


async def test_get_vehicle_by_asset_number_found() -> None:
    out = await get_vehicle_by_asset_number.ainvoke({"asset_number": "V-2017-0007"})
    assert "V-2017-0007" in out
    assert '"AssetNumber": "V-2017-0007"' in out


async def test_get_vehicle_by_asset_number_missing() -> None:
    out = await get_vehicle_by_asset_number.ainvoke({"asset_number": "V-9999-9999"})
    assert out == "No vehicle found with asset number V-9999-9999."


async def test_search_vehicles_by_department_returns_matches() -> None:
    out = await search_vehicles.ainvoke({"department": "Public Works"})
    assert out.startswith("Found ")
    assert "Public Works" in out


async def test_search_vehicles_invalid_status_returns_friendly_error() -> None:
    out = await search_vehicles.ainvoke({"status": "Melted"})
    assert out.startswith("Invalid value 'Melted'")
    # Error string advertises the valid values so the LLM can self-correct.
    assert "Active" in out


async def test_search_vehicles_no_matches() -> None:
    out = await search_vehicles.ainvoke({"make": "Rivian"})
    assert out == "No vehicles found matching the specified criteria."


async def test_get_vehicles_by_high_maintenance_cost_ranked() -> None:
    out = await get_vehicles_by_high_maintenance_cost.ainvoke({"top_n": 3})
    assert "Top 3 vehicles by maintenance cost" in out
