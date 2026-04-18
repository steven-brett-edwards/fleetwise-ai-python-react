"""Part repository -- parity with `IPartRepository`."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.domain.entities import Part


async def get_all(session: AsyncSession) -> list[Part]:
    stmt = select(Part).order_by(Part.category, Part.name)
    return list((await session.execute(stmt)).scalars().all())


async def get_below_reorder_threshold(session: AsyncSession) -> list[Part]:
    stmt = (
        select(Part)
        .where(Part.quantity_in_stock <= Part.reorder_threshold)
        .order_by(Part.quantity_in_stock)
    )
    return list((await session.execute(stmt)).scalars().all())
