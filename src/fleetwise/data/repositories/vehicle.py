"""Vehicle repository -- async functions, method-for-method parity with `IVehicleRepository`."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fleetwise.domain.entities import MaintenanceRecord, Vehicle
from fleetwise.domain.enums import FuelType, VehicleStatus
from fleetwise.domain.models import FleetSummary, VehicleMaintenanceCost


async def get_all(
    session: AsyncSession,
    *,
    status: VehicleStatus | None = None,
    department: str | None = None,
    fuel_type: FuelType | None = None,
) -> list[Vehicle]:
    stmt = select(Vehicle)
    if status is not None:
        stmt = stmt.where(Vehicle.status == status)
    if department:
        stmt = stmt.where(Vehicle.department == department)
    if fuel_type is not None:
        stmt = stmt.where(Vehicle.fuel_type == fuel_type)
    stmt = stmt.order_by(Vehicle.asset_number)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, vehicle_id: int) -> Vehicle | None:
    stmt = (
        select(Vehicle)
        .options(selectinload(Vehicle.maintenance_schedules))
        .where(Vehicle.id == vehicle_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_asset_number(session: AsyncSession, asset_number: str) -> Vehicle | None:
    stmt = (
        select(Vehicle)
        .options(selectinload(Vehicle.maintenance_schedules))
        .where(Vehicle.asset_number == asset_number)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def search(
    session: AsyncSession,
    *,
    make: str | None = None,
    model: str | None = None,
    department: str | None = None,
    status: VehicleStatus | None = None,
    fuel_type: FuelType | None = None,
) -> list[Vehicle]:
    stmt = select(Vehicle)
    if make:
        stmt = stmt.where(func.lower(Vehicle.make).contains(make.lower()))
    if model:
        stmt = stmt.where(func.lower(Vehicle.model).contains(model.lower()))
    if department:
        stmt = stmt.where(func.lower(Vehicle.department).contains(department.lower()))
    if status is not None:
        stmt = stmt.where(Vehicle.status == status)
    if fuel_type is not None:
        stmt = stmt.where(Vehicle.fuel_type == fuel_type)
    stmt = stmt.order_by(Vehicle.asset_number)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_fleet_summary(session: AsyncSession) -> FleetSummary:
    """Group-by-and-count of the whole fleet.

    Done in Python (Counter) rather than SQL. Dataset is tiny (35 rows),
    pulling it into memory once and using `collections.Counter` is clearer
    than three separate GROUP BY queries.
    """
    result = await session.execute(select(Vehicle))
    vehicles = list(result.scalars().all())

    return FleetSummary(
        total_vehicles=len(vehicles),
        by_status=dict(Counter(v.status.value for v in vehicles)),
        by_fuel_type=dict(Counter(v.fuel_type.value for v in vehicles)),
        by_department=dict(Counter(v.department for v in vehicles)),
    )


async def get_vehicles_by_maintenance_cost(
    session: AsyncSession, top_n: int = 10
) -> list[VehicleMaintenanceCost]:
    """Top-N vehicles by lifetime maintenance cost.

    The .NET version aggregates in memory because EF's SQLite provider
    can't translate GROUP BY + SUM(decimal) + ORDER BY. SQLAlchemy's
    aiosqlite driver actually handles this SQL-side correctly -- we could
    push the aggregation down. Keeping the in-memory pattern for clarity
    and because the dataset is small; Phase 7's integration tests pin the
    behavior either way.
    """
    rows = (
        await session.execute(select(MaintenanceRecord.vehicle_id, MaintenanceRecord.cost))
    ).all()
    if not rows:
        return []

    totals: dict[int, tuple[Decimal, int]] = {}
    for vehicle_id, cost in rows:
        current_total, count = totals.get(vehicle_id, (Decimal(0), 0))
        totals[vehicle_id] = (current_total + cost, count + 1)

    ranked = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)[:top_n]
    if not ranked:
        return []

    vehicle_ids = [vid for vid, _ in ranked]
    vehicle_rows = (
        await session.execute(select(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
    ).scalars()
    vehicles_by_id = {v.id: v for v in vehicle_rows}

    return [
        VehicleMaintenanceCost(
            vehicle_id=vid,
            asset_number=vehicles_by_id[vid].asset_number,
            year=vehicles_by_id[vid].year,
            make=vehicles_by_id[vid].make,
            model=vehicles_by_id[vid].model,
            total_maintenance_cost=total,
            record_count=count,
        )
        for vid, (total, count) in ranked
        if vid in vehicles_by_id
    ]
