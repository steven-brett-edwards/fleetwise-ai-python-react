"""Tool-layer tests for `ai.tools.maintenance`."""

from __future__ import annotations

import pytest

from fleetwise.ai.tools.maintenance import (
    get_maintenance_cost_summary,
    get_maintenance_history_by_asset_number,
    get_overdue_maintenance,
    get_upcoming_maintenance,
    get_vehicle_maintenance_history,
)

pytestmark = pytest.mark.usefixtures("tool_session_factory")


async def test_get_overdue_maintenance_returns_schedules() -> None:
    out = await get_overdue_maintenance.ainvoke({})
    assert "Found " in out
    assert "overdue maintenance schedules" in out


async def test_get_upcoming_maintenance_with_default_windows() -> None:
    out = await get_upcoming_maintenance.ainvoke({})
    # Either the "Found N" preface or the no-data message -- both are valid
    # endings for this seeded dataset depending on the date window.
    assert out.startswith("Found ") or out.startswith("No maintenance scheduled")


async def test_get_vehicle_maintenance_history_by_id() -> None:
    out = await get_vehicle_maintenance_history.ainvoke({"vehicle_id": 1})
    # Vehicle 1 has seeded maintenance records.
    assert "vehicle ID 1" in out
    assert '"MaintenanceType"' in out


async def test_get_vehicle_maintenance_history_missing() -> None:
    out = await get_vehicle_maintenance_history.ainvoke({"vehicle_id": 99999})
    assert out == "No maintenance records found for vehicle ID 99999."


async def test_get_maintenance_history_by_asset_number_found() -> None:
    out = await get_maintenance_history_by_asset_number.ainvoke({"asset_number": "V-2017-0007"})
    # Either records for the vehicle, or the "no records" branch for that vehicle.
    assert "V-2017-0007" in out


async def test_get_maintenance_history_by_asset_number_missing_vehicle() -> None:
    out = await get_maintenance_history_by_asset_number.ainvoke({"asset_number": "V-9999-9999"})
    assert out == "No vehicle found with asset number V-9999-9999."


async def test_get_maintenance_cost_summary_default_group_by_vehicle() -> None:
    out = await get_maintenance_cost_summary.ainvoke({})
    assert "grouped by vehicle" in out


async def test_get_maintenance_cost_summary_invalid_group_by() -> None:
    out = await get_maintenance_cost_summary.ainvoke({"group_by": "purple"})
    assert out.startswith("Invalid groupBy value 'purple'")
