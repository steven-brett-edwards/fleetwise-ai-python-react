"""Maintenance repository -- parity with `IMaintenanceRepository`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fleetwise.domain.entities import MaintenanceRecord, MaintenanceSchedule, Vehicle
from fleetwise.domain.models import MaintenanceCostGroup


def _utc_naive_now() -> datetime:
    """Match the .NET `DateTime.UtcNow` (naive UTC) used on the schedule columns."""
    return datetime.now(UTC).replace(tzinfo=None)


async def get_by_vehicle_id(session: AsyncSession, vehicle_id: int) -> list[MaintenanceRecord]:
    stmt = (
        select(MaintenanceRecord)
        .where(MaintenanceRecord.vehicle_id == vehicle_id)
        .order_by(MaintenanceRecord.performed_date.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_overdue_schedules(session: AsyncSession) -> list[MaintenanceSchedule]:
    """Past due by date OR by mileage.

    Does the comparison in SQL via a correlated join to Vehicle so we can
    filter large schedule tables without pulling everything into memory.
    Eager-loads the Vehicle relationship because the API response shape
    references it.
    """
    now = _utc_naive_now()
    stmt = (
        select(MaintenanceSchedule)
        .join(Vehicle, MaintenanceSchedule.vehicle_id == Vehicle.id)
        .options(selectinload(MaintenanceSchedule.vehicle))
        .where(
            or_(
                MaintenanceSchedule.next_due_date < now,
                Vehicle.current_mileage >= MaintenanceSchedule.next_due_mileage,
            )
        )
        .order_by(MaintenanceSchedule.next_due_date)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_upcoming_schedules(
    session: AsyncSession, within_days: int = 30, within_miles: int = 5000
) -> list[MaintenanceSchedule]:
    """Due within the date or mileage window but not yet past due."""
    now = _utc_naive_now()
    cutoff_date = now + timedelta(days=within_days)

    stmt = (
        select(MaintenanceSchedule)
        .join(Vehicle, MaintenanceSchedule.vehicle_id == Vehicle.id)
        .options(selectinload(MaintenanceSchedule.vehicle))
        .where(
            or_(
                (MaintenanceSchedule.next_due_date >= now)
                & (MaintenanceSchedule.next_due_date <= cutoff_date),
                (Vehicle.current_mileage >= MaintenanceSchedule.next_due_mileage - within_miles)
                & (Vehicle.current_mileage < MaintenanceSchedule.next_due_mileage),
            )
        )
        .order_by(MaintenanceSchedule.next_due_date)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_cost_summary(
    session: AsyncSession, group_by: str = "vehicle"
) -> list[MaintenanceCostGroup]:
    """Aggregate maintenance cost, grouped by vehicle / type / month.

    In-memory aggregation mirrors the .NET implementation. Dataset is
    small; readability wins over squeezing out a SQL GROUP BY.
    """
    stmt = select(
        MaintenanceRecord.cost,
        MaintenanceRecord.performed_date,
        MaintenanceRecord.maintenance_type,
        Vehicle.asset_number,
    ).join(Vehicle, MaintenanceRecord.vehicle_id == Vehicle.id)
    rows = (await session.execute(stmt)).all()

    match group_by.lower():
        case "type":
            pairs = ((r.maintenance_type.value, r.cost) for r in rows)
            return _aggregate(pairs, order_desc_by="total")
        case "month":
            pairs = (
                (f"{r.performed_date.year}-{r.performed_date.month:02d}", r.cost) for r in rows
            )
            return _aggregate(pairs, order_desc_by="key")
        case _:
            pairs = ((r.asset_number, r.cost) for r in rows)
            return _aggregate(pairs, order_desc_by="total")


def _aggregate(
    pairs: Iterable[tuple[str, Decimal]],
    *,
    order_desc_by: str,
) -> list[MaintenanceCostGroup]:
    totals: dict[str, Decimal] = {}
    counts: Counter[str] = Counter()
    for key, cost in pairs:
        totals[key] = totals.get(key, Decimal(0)) + cost
        counts[key] += 1
    groups = [
        MaintenanceCostGroup(group_key=k, total_cost=totals[k], record_count=counts[k])
        for k in totals
    ]
    if order_desc_by == "key":
        groups.sort(key=lambda g: g.group_key, reverse=True)
    else:
        groups.sort(key=lambda g: g.total_cost, reverse=True)
    return groups
