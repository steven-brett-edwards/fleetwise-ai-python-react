"""Seed the database from the JSON dumps in `src/fleetwise/data/seed_data/`.

The JSON files were produced by dumping the .NET edition's SQLite DB with
`sqlite3 -json`. Reusing those dumps guarantees exact parity with the .NET
app's 35-vehicle demo fleet (asset numbers, VINs, dates, costs) so
screenshots and demo scripts remain comparable across editions.

Seeding is idempotent: `seed_if_empty` runs only when the Vehicles table
is empty. On Render the fleet DB sits on a persistent volume, so the seed
runs once on first deploy and never again.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.domain.entities import (
    MaintenanceRecord,
    MaintenanceSchedule,
    Part,
    Vehicle,
    WorkOrder,
)
from fleetwise.domain.enums import (
    FuelType,
    MaintenanceType,
    Priority,
    VehicleStatus,
    WorkOrderStatus,
)

SEED_DIR = Path(__file__).parent / "seed_data"

# SQLite stores datetimes as "YYYY-MM-DD HH:MM:SS"; the .NET dump preserves
# that format. We parse it back to a naive `datetime` -- the .NET side was
# UTC-naive too, so no timezone shifting is needed.
_SQLITE_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.strptime(value, _SQLITE_DATETIME_FMT)


def _parse_decimal(value: str | int | float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _load_json(name: str) -> list[dict[str, Any]]:
    path = SEED_DIR / name
    with path.open(encoding="utf-8") as fh:
        loaded: list[dict[str, Any]] = json.load(fh)
        return loaded


def _build_vehicles(rows: list[dict[str, Any]]) -> list[Vehicle]:
    return [
        Vehicle(
            id=row["Id"],
            asset_number=row["AssetNumber"],
            vin=row["VIN"],
            year=row["Year"],
            make=row["Make"],
            model=row["Model"],
            fuel_type=FuelType(row["FuelType"]),
            status=VehicleStatus(row["Status"]),
            department=row["Department"],
            assigned_driver=row["AssignedDriver"],
            current_mileage=row["CurrentMileage"],
            acquisition_date=_parse_dt(row["AcquisitionDate"]),
            acquisition_cost=_parse_decimal(row["AcquisitionCost"]),
            license_plate=row["LicensePlate"],
            location=row["Location"],
            notes=row["Notes"],
        )
        for row in rows
    ]


def _build_parts(rows: list[dict[str, Any]]) -> list[Part]:
    return [
        Part(
            id=row["Id"],
            part_number=row["PartNumber"],
            name=row["Name"],
            category=row["Category"],
            quantity_in_stock=row["QuantityInStock"],
            reorder_threshold=row["ReorderThreshold"],
            unit_cost=_parse_decimal(row["UnitCost"]),
            location=row["Location"],
        )
        for row in rows
    ]


def _build_work_orders(rows: list[dict[str, Any]]) -> list[WorkOrder]:
    return [
        WorkOrder(
            id=row["Id"],
            work_order_number=row["WorkOrderNumber"],
            vehicle_id=row["VehicleId"],
            status=WorkOrderStatus(row["Status"]),
            priority=Priority(row["Priority"]),
            description=row["Description"],
            requested_date=_parse_dt(row["RequestedDate"]),
            completed_date=_parse_dt(row["CompletedDate"]),
            assigned_technician=row["AssignedTechnician"],
            labor_hours=_parse_decimal(row["LaborHours"]),
            total_cost=_parse_decimal(row["TotalCost"]),
            notes=row["Notes"],
        )
        for row in rows
    ]


def _build_maintenance_records(rows: list[dict[str, Any]]) -> list[MaintenanceRecord]:
    return [
        MaintenanceRecord(
            id=row["Id"],
            vehicle_id=row["VehicleId"],
            work_order_id=row["WorkOrderId"],
            maintenance_type=MaintenanceType(row["MaintenanceType"]),
            performed_date=_parse_dt(row["PerformedDate"]),
            mileage_at_service=row["MileageAtService"],
            description=row["Description"],
            cost=_parse_decimal(row["Cost"]),
            technician_name=row["TechnicianName"],
        )
        for row in rows
    ]


def _build_maintenance_schedules(rows: list[dict[str, Any]]) -> list[MaintenanceSchedule]:
    return [
        MaintenanceSchedule(
            id=row["Id"],
            vehicle_id=row["VehicleId"],
            maintenance_type=MaintenanceType(row["MaintenanceType"]),
            interval_miles=row["IntervalMiles"],
            interval_days=row["IntervalDays"],
            last_completed_date=_parse_dt(row["LastCompletedDate"]),
            last_completed_mileage=row["LastCompletedMileage"],
            next_due_mileage=row["NextDueMileage"],
            next_due_date=_parse_dt(row["NextDueDate"]),
        )
        for row in rows
    ]


async def vehicle_count(session: AsyncSession) -> int:
    """Row count helper used by seed idempotency + smoke tests."""
    result = await session.execute(select(func.count()).select_from(Vehicle))
    return int(result.scalar_one())


async def seed_if_empty(session: AsyncSession) -> bool:
    """Populate the DB from JSON dumps only if Vehicles is empty.

    Returns True if seeding ran, False if the DB was already populated.
    Parents are inserted before children to keep FK references valid in
    the same transaction.
    """
    if await vehicle_count(session) > 0:
        return False

    # Parents first: vehicles + parts have no FK deps.
    session.add_all(_build_vehicles(_load_json("vehicles.json")))
    session.add_all(_build_parts(_load_json("parts.json")))
    await session.flush()

    # Work orders depend on vehicles.
    session.add_all(_build_work_orders(_load_json("work_orders.json")))
    await session.flush()

    # Maintenance records depend on vehicles and (optionally) work orders.
    session.add_all(_build_maintenance_records(_load_json("maintenance_records.json")))
    session.add_all(_build_maintenance_schedules(_load_json("maintenance_schedules.json")))

    await session.commit()
    return True
