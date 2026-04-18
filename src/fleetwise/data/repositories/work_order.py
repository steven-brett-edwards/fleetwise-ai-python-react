"""Work order repository -- parity with `IWorkOrderRepository`.

`Priority` is a string-backed enum, so the DB-side ORDER BY sorts
alphabetically ("Critical" < "High" < "Low" < "Medium"). The .NET version
gets the same accidental-alphabetic ordering for the same reason; if a
true priority ranking becomes necessary, both editions need the same fix.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fleetwise.domain.entities import WorkOrder
from fleetwise.domain.enums import WorkOrderStatus


async def get_all(
    session: AsyncSession, *, status: WorkOrderStatus | None = None
) -> list[WorkOrder]:
    stmt = select(WorkOrder).options(selectinload(WorkOrder.vehicle))
    if status is not None:
        stmt = stmt.where(WorkOrder.status == status)
    stmt = stmt.order_by(WorkOrder.requested_date.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get_by_id(session: AsyncSession, work_order_id: int) -> WorkOrder | None:
    stmt = (
        select(WorkOrder)
        .options(selectinload(WorkOrder.vehicle))
        .where(WorkOrder.id == work_order_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_work_order_number(
    session: AsyncSession, work_order_number: str
) -> WorkOrder | None:
    stmt = (
        select(WorkOrder)
        .options(selectinload(WorkOrder.vehicle))
        .where(WorkOrder.work_order_number == work_order_number)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_vehicle_id(session: AsyncSession, vehicle_id: int) -> list[WorkOrder]:
    stmt = (
        select(WorkOrder)
        .options(selectinload(WorkOrder.vehicle))
        .where(WorkOrder.vehicle_id == vehicle_id)
        .order_by(WorkOrder.requested_date.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_open_work_orders(session: AsyncSession) -> list[WorkOrder]:
    """Active work (not Completed, not Cancelled), ordered priority desc then date desc."""
    stmt = (
        select(WorkOrder)
        .options(selectinload(WorkOrder.vehicle))
        .where(WorkOrder.status.notin_([WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED]))
        .order_by(WorkOrder.priority.desc(), WorkOrder.requested_date.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
