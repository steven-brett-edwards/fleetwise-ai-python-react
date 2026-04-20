"""Pydantic DTOs — the wire shape of every API response.

The goal is byte-identical JSON output to the .NET edition so the existing
Angular client can point at this API unchanged (migration plan §2d).

Two conventions you'll see throughout:

- `ConfigDict(alias_generator=to_pascal, populate_by_name=True, from_attributes=True)`
  gives us snake_case Python attributes with PascalCase JSON keys, populated
  directly from SQLAlchemy entity attributes (or our domain dataclasses).
- `field_serializer` for `Decimal` fields emits a JSON number (via `float`)
  rather than Pydantic v2's default stringified Decimal. .NET's
  `System.Text.Json` writes decimals as numbers; the Angular client parses
  them as numbers; matching here keeps the wire format identical. The two-
  decimal money values round-trip through float64 without precision loss.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_pascal

from fleetwise.domain.enums import (
    FuelType,
    MaintenanceType,
    Priority,
    VehicleStatus,
    WorkOrderStatus,
)


class _WireModel(BaseModel):
    """Shared config: PascalCase wire keys, ORM-attribute population."""

    model_config = ConfigDict(
        alias_generator=to_pascal,
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=True,
    )


def _decimal_to_number(value: Decimal | None) -> float | None:
    """Serialize `Decimal` as a JSON number, not a string (parity with .NET)."""
    return float(value) if value is not None else None


class VehicleResponse(_WireModel):
    """Matches the shape the .NET API serializes for a `Vehicle` entity."""

    id: int
    asset_number: str
    vin: str
    year: int
    make: str
    model: str
    fuel_type: FuelType
    status: VehicleStatus
    department: str
    assigned_driver: str | None
    current_mileage: int
    acquisition_date: datetime
    acquisition_cost: Decimal
    license_plate: str
    location: str
    notes: str | None

    @field_serializer("acquisition_cost", when_used="json")
    def _cost(self, v: Decimal) -> float:
        return float(v)


class MaintenanceRecordResponse(_WireModel):
    id: int
    vehicle_id: int
    work_order_id: int | None
    maintenance_type: MaintenanceType
    performed_date: datetime
    mileage_at_service: int
    description: str
    cost: Decimal
    technician_name: str

    @field_serializer("cost", when_used="json")
    def _cost(self, v: Decimal) -> float:
        return float(v)


class WorkOrderResponse(_WireModel):
    id: int
    work_order_number: str
    vehicle_id: int
    status: WorkOrderStatus
    priority: Priority
    description: str
    requested_date: datetime
    completed_date: datetime | None
    assigned_technician: str | None
    labor_hours: Decimal | None
    total_cost: Decimal | None
    notes: str | None

    @field_serializer("labor_hours", "total_cost", when_used="json")
    def _money(self, v: Decimal | None) -> float | None:
        return _decimal_to_number(v)


class FleetSummaryResponse(_WireModel):
    total_vehicles: int
    by_status: dict[str, int]
    by_fuel_type: dict[str, int]
    by_department: dict[str, int]


class MaintenanceScheduleItemResponse(_WireModel):
    """Projection shape matching MaintenanceController's overdue/upcoming payload.

    The .NET controllers flatten `Vehicle` navigation properties into
    sibling fields (`VehicleAssetNumber`, `VehicleDescription`,
    `CurrentMileage`) -- we do the same so the Angular client doesn't have
    to thread through a nested object.
    """

    id: int
    vehicle_id: int
    vehicle_asset_number: str
    vehicle_description: str
    maintenance_type: MaintenanceType
    next_due_date: datetime | None
    next_due_mileage: int | None
    current_mileage: int
    last_completed_date: datetime | None = None
    last_completed_mileage: int | None = None
