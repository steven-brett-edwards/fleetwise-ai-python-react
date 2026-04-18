"""Work order repository tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.repositories import work_order as work_order_repo
from fleetwise.domain.enums import WorkOrderStatus


async def test_get_all_orders_by_requested_date_desc(session: AsyncSession) -> None:
    orders = await work_order_repo.get_all(session)
    assert len(orders) == 36
    dates = [wo.requested_date for wo in orders]
    assert dates == sorted(dates, reverse=True)


async def test_get_all_filters_by_status(session: AsyncSession) -> None:
    completed = await work_order_repo.get_all(session, status=WorkOrderStatus.COMPLETED)
    assert completed
    assert all(wo.status is WorkOrderStatus.COMPLETED for wo in completed)


async def test_get_by_id_loads_vehicle_relationship(session: AsyncSession) -> None:
    wo = await work_order_repo.get_by_id(session, 1)
    assert wo is not None
    assert wo.vehicle is not None
    assert wo.vehicle.asset_number.startswith("V-")


async def test_get_by_id_returns_none_for_missing(session: AsyncSession) -> None:
    assert await work_order_repo.get_by_id(session, 99_999) is None


async def test_get_by_work_order_number(session: AsyncSession) -> None:
    wo = await work_order_repo.get_by_work_order_number(session, "WO-2025-00001")
    assert wo is not None
    assert wo.id == 1


async def test_get_by_vehicle_id_orders_by_requested_date_desc(session: AsyncSession) -> None:
    orders = await work_order_repo.get_by_vehicle_id(session, vehicle_id=1)
    assert all(wo.vehicle_id == 1 for wo in orders)
    dates = [wo.requested_date for wo in orders]
    assert dates == sorted(dates, reverse=True)


async def test_open_work_orders_exclude_completed_and_cancelled(session: AsyncSession) -> None:
    open_orders = await work_order_repo.get_open_work_orders(session)
    statuses = {wo.status for wo in open_orders}
    assert WorkOrderStatus.COMPLETED not in statuses
    assert WorkOrderStatus.CANCELLED not in statuses
