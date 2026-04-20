"""DTO wire-format unit tests.

These pin the two things that always drift when porting .NET -> Python:
PascalCase JSON keys and Decimal-as-number serialization. They run without
a DB so they're cheap to keep in the fast unit tier.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from fleetwise.domain.dto import (
    FleetSummaryResponse,
    VehicleResponse,
    WorkOrderResponse,
)
from fleetwise.domain.enums import FuelType, Priority, VehicleStatus, WorkOrderStatus


def _sample_vehicle() -> VehicleResponse:
    return VehicleResponse(
        id=1,
        asset_number="V-2019-0042",
        vin="1HGCM82633A004352",
        year=2019,
        make="Ford",
        model="F-150",
        fuel_type=FuelType.GASOLINE,
        status=VehicleStatus.ACTIVE,
        department="Public Works",
        assigned_driver=None,
        current_mileage=75_000,
        acquisition_date=datetime(2019, 3, 15),
        acquisition_cost=Decimal("32500.00"),
        license_plate="GOV-1234",
        location="Yard A",
        notes=None,
    )


def test_vehicle_response_serializes_pascalcase_keys() -> None:
    data = json.loads(_sample_vehicle().model_dump_json(by_alias=True))
    assert "AssetNumber" in data
    assert "FuelType" in data
    assert "CurrentMileage" in data
    assert "AcquisitionDate" in data
    # No snake_case leaks.
    assert not any("_" in k for k in data)


def test_vehicle_response_decimal_is_json_number() -> None:
    """.NET `JsonSerializer` emits decimals as numbers; we match."""
    raw = _sample_vehicle().model_dump_json(by_alias=True)
    data = json.loads(raw)
    assert isinstance(data["AcquisitionCost"], int | float)
    # Round-trips cleanly at 2-decimal precision.
    assert data["AcquisitionCost"] == 32500.0


def test_vehicle_response_enum_serializes_as_string_value() -> None:
    data = json.loads(_sample_vehicle().model_dump_json(by_alias=True))
    assert data["FuelType"] == "Gasoline"
    assert data["Status"] == "Active"


def test_vehicle_response_datetime_is_isoformat() -> None:
    data = json.loads(_sample_vehicle().model_dump_json(by_alias=True))
    assert data["AcquisitionDate"] == "2019-03-15T00:00:00"


def test_work_order_nullable_money_serializes_as_null() -> None:
    wo = WorkOrderResponse(
        id=1,
        work_order_number="WO-0001",
        vehicle_id=1,
        status=WorkOrderStatus.OPEN,
        priority=Priority.HIGH,
        description="Replace brake pads",
        requested_date=datetime(2026, 1, 1),
        completed_date=None,
        assigned_technician=None,
        labor_hours=None,
        total_cost=None,
        notes=None,
    )
    data = json.loads(wo.model_dump_json(by_alias=True))
    assert data["LaborHours"] is None
    assert data["TotalCost"] is None


def test_fleet_summary_keeps_group_keys_verbatim() -> None:
    summary = FleetSummaryResponse(
        total_vehicles=35,
        by_status={"Active": 30, "InShop": 5},
        by_fuel_type={"Gasoline": 20, "Diesel": 15},
        by_department={"Public Works": 35},
    )
    data = json.loads(summary.model_dump_json(by_alias=True))
    assert data["TotalVehicles"] == 35
    # Group-key dicts are passed through unchanged (PascalCase enum values
    # on the left, ints on the right).
    assert data["ByStatus"] == {"Active": 30, "InShop": 5}
