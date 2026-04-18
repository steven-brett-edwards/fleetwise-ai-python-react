"""Domain-level value types returned by repository aggregations.

These are plain dataclasses, not SQLAlchemy entities and not Pydantic
DTOs -- the API layer maps them to `Pydantic` response models in Phase 2.
Keeping them here, in the domain layer, keeps the data layer's return
types free of any web-framework knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FleetSummary:
    total_vehicles: int
    by_status: dict[str, int]
    by_fuel_type: dict[str, int]
    by_department: dict[str, int]


@dataclass(frozen=True, slots=True)
class VehicleMaintenanceCost:
    vehicle_id: int
    asset_number: str
    year: int
    make: str
    model: str
    total_maintenance_cost: Decimal
    record_count: int


@dataclass(frozen=True, slots=True)
class MaintenanceCostGroup:
    group_key: str
    total_cost: Decimal
    record_count: int
