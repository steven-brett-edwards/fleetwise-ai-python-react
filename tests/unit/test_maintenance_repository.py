"""Maintenance repository tests.

Exercise the date/mileage-window filters for schedules and the three
group-by paths on the cost summary. The date-based filters use the real
clock, so we compare against `>= 0` / ordering invariants rather than
exact counts to keep tests from drifting with the passage of time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.repositories import maintenance as maintenance_repo


async def test_get_by_vehicle_id_returns_records_newest_first(session: AsyncSession) -> None:
    records = await maintenance_repo.get_by_vehicle_id(session, vehicle_id=1)
    assert records, "vehicle 1 should have maintenance records"
    assert all(r.vehicle_id == 1 for r in records)
    dates = [r.performed_date for r in records]
    assert dates == sorted(dates, reverse=True)


async def test_get_by_vehicle_id_returns_empty_for_unknown_vehicle(session: AsyncSession) -> None:
    assert await maintenance_repo.get_by_vehicle_id(session, vehicle_id=99_999) == []


async def test_overdue_schedules_all_satisfy_overdue_predicate(session: AsyncSession) -> None:
    overdue = await maintenance_repo.get_overdue_schedules(session)
    now = datetime.now(UTC).replace(tzinfo=None)
    for s in overdue:
        by_date = s.next_due_date is not None and s.next_due_date < now
        by_mileage = (
            s.next_due_mileage is not None and s.vehicle.current_mileage >= s.next_due_mileage
        )
        assert by_date or by_mileage


async def test_upcoming_schedules_fall_inside_date_or_mileage_window(
    session: AsyncSession,
) -> None:
    """Parity with the .NET query: each upcoming schedule is either due inside
    the next 30 days by date, OR inside the next 5,000 miles by odometer.
    Note that overdue-by-date can still match the mileage branch -- that
    overlap is a .NET-side quirk we preserve on purpose."""
    upcoming = await maintenance_repo.get_upcoming_schedules(session)
    now = datetime.now(UTC).replace(tzinfo=None)
    cutoff = now + timedelta(days=30)
    for s in upcoming:
        by_date = s.next_due_date is not None and now <= s.next_due_date <= cutoff
        by_mileage = s.next_due_mileage is not None and (
            s.next_due_mileage - 5000 <= s.vehicle.current_mileage < s.next_due_mileage
        )
        assert by_date or by_mileage


async def test_cost_summary_group_by_vehicle_orders_by_total_desc(session: AsyncSession) -> None:
    groups = await maintenance_repo.get_cost_summary(session, group_by="vehicle")
    assert groups
    assert [g.total_cost for g in groups] == sorted((g.total_cost for g in groups), reverse=True)
    assert all(g.total_cost > Decimal(0) for g in groups)


async def test_cost_summary_group_by_type(session: AsyncSession) -> None:
    groups = await maintenance_repo.get_cost_summary(session, group_by="type")
    keys = [g.group_key for g in groups]
    assert "OilChange" in keys


async def test_cost_summary_group_by_month_orders_by_key_desc(session: AsyncSession) -> None:
    groups = await maintenance_repo.get_cost_summary(session, group_by="month")
    keys = [g.group_key for g in groups]
    assert keys == sorted(keys, reverse=True)
    assert all(len(k) == 7 and k[4] == "-" for k in keys)  # "YYYY-MM"


async def test_cost_summary_unknown_group_by_defaults_to_vehicle(session: AsyncSession) -> None:
    default = await maintenance_repo.get_cost_summary(session, group_by="not-a-valid-group")
    by_vehicle = await maintenance_repo.get_cost_summary(session, group_by="vehicle")
    assert [g.group_key for g in default] == [g.group_key for g in by_vehicle]
