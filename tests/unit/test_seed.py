"""Seed integrity tests.

The .NET edition has exact counts that demo screenshots and documentation
rely on (35 vehicles, 45 parts, etc.). If the JSON dumps get corrupted or
the loader drops rows, these tests catch it before the fleet summary
starts lying on the dashboard.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.seed import seed_if_empty, vehicle_count
from fleetwise.domain.entities import (
    MaintenanceRecord,
    MaintenanceSchedule,
    Part,
    Vehicle,
    WorkOrder,
)
from fleetwise.domain.enums import FuelType, VehicleStatus


async def test_seed_populates_all_five_tables_with_expected_counts(
    session: AsyncSession, expected_seed_counts: dict[str, int]
) -> None:
    counts = {
        "vehicles": (await session.execute(select(func.count()).select_from(Vehicle))).scalar_one(),
        "parts": (await session.execute(select(func.count()).select_from(Part))).scalar_one(),
        "work_orders": (
            await session.execute(select(func.count()).select_from(WorkOrder))
        ).scalar_one(),
        "maintenance_records": (
            await session.execute(select(func.count()).select_from(MaintenanceRecord))
        ).scalar_one(),
        "maintenance_schedules": (
            await session.execute(select(func.count()).select_from(MaintenanceSchedule))
        ).scalar_one(),
    }
    assert counts == expected_seed_counts


async def test_seed_is_idempotent(session: AsyncSession) -> None:
    """Re-seeding a populated DB returns False and does not duplicate rows."""
    first_count = await vehicle_count(session)
    ran = await seed_if_empty(session)
    assert ran is False
    assert await vehicle_count(session) == first_count


async def test_vehicle_v_2019_0001_round_trips_from_net_dump(session: AsyncSession) -> None:
    """Spot-check one vehicle to guard against silent column-mapping regressions."""
    result = await session.execute(select(Vehicle).where(Vehicle.asset_number == "V-2019-0001"))
    vehicle = result.scalar_one()

    assert vehicle.vin == "1FTEW1EP5KFA00001"
    assert vehicle.year == 2019
    assert vehicle.make == "Ford"
    assert vehicle.model == "F-150 XL"
    assert vehicle.fuel_type is FuelType.GASOLINE
    assert vehicle.status is VehicleStatus.ACTIVE
    assert vehicle.department == "Public Works"
    assert vehicle.current_mileage == 87432
