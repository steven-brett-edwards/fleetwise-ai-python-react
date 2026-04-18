"""Part repository tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.repositories import part as part_repo


async def test_get_all_orders_by_category_then_name(session: AsyncSession) -> None:
    parts = await part_repo.get_all(session)
    assert len(parts) == 45
    assert parts == sorted(parts, key=lambda p: (p.category, p.name))


async def test_below_reorder_threshold_returns_only_low_stock(session: AsyncSession) -> None:
    low = await part_repo.get_below_reorder_threshold(session)
    assert all(p.quantity_in_stock <= p.reorder_threshold for p in low)
    # The .NET seed puts exactly 7 parts below threshold.
    assert len(low) == 7
    # Ordered by quantity ascending so the most-urgent reorder is first.
    assert [p.quantity_in_stock for p in low] == sorted(p.quantity_in_stock for p in low)
