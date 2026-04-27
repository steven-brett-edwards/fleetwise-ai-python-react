"""SQLite aggregation regression tests.

The .NET edition got bitten by EF Core's SQLite provider being unable to
translate `GROUP BY + SUM(decimal) + ORDER BY` -- queries either threw
or silently returned wrong values, so the .NET repos all aggregate in
memory. SQLAlchemy's aiosqlite driver actually handles this combination
correctly, which means our in-memory aggregation is a *choice* (small
dataset, clearer code), not a workaround.

This module pins that distinction. If a future SQLAlchemy bump regresses
on SQLite numeric aggregation, these tests fail loudly before anyone
ships a "wait, why is the wire format empty" surprise.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.repositories.vehicle import get_vehicles_by_maintenance_cost
from fleetwise.domain.entities import MaintenanceRecord


@pytest.mark.asyncio
async def test_sql_groupby_sum_orderby_matches_python_aggregation(
    session: AsyncSession,
) -> None:
    """SQL-side GROUP BY + SUM(Numeric) + ORDER BY agrees with the Python path.

    We compute the same top-5-vehicles-by-lifetime-maintenance-cost two ways:
    SQL-side via a real GROUP BY + SUM + ORDER BY, and Python-side via the
    repository's in-memory aggregation. They must agree on both the ranking
    and the totals.
    """
    stmt = (
        select(
            MaintenanceRecord.vehicle_id,
            func.sum(MaintenanceRecord.cost).label("total"),
        )
        .group_by(MaintenanceRecord.vehicle_id)
        .order_by(func.sum(MaintenanceRecord.cost).desc())
        .limit(5)
    )
    sql_rows = (await session.execute(stmt)).all()

    # The SQL path must return something against the seeded fleet -- if this
    # is empty the regression has already happened (silent zero-row return).
    assert len(sql_rows) == 5, (
        f"Expected 5 ranked vehicles from SQL aggregation, got {len(sql_rows)}"
    )

    python_path = await get_vehicles_by_maintenance_cost(session, top_n=5)
    assert len(python_path) == 5

    sql_pairs = [(int(vid), Decimal(str(total))) for vid, total in sql_rows]
    py_pairs = [(p.vehicle_id, p.total_maintenance_cost) for p in python_path]

    assert sql_pairs == py_pairs, (
        "SQL aggregation diverged from Python aggregation -- one of the two "
        "paths is wrong. Pinned by this test because EF on SQLite was."
    )


@pytest.mark.asyncio
async def test_sql_sum_numeric_preserves_two_decimal_precision(
    session: AsyncSession,
) -> None:
    """`SUM(Numeric(18, 2))` returns a Decimal-shaped value, not a lossy float.

    Money fields are `Numeric(18, 2)` precisely so totals don't drift through
    float64. Aiosqlite hands the value back as a Python `Decimal`; this test
    pins that contract -- if a future driver bump turns this into a float we
    want to catch it before the wire format starts emitting `199.99000003`.
    """
    stmt = select(func.sum(MaintenanceRecord.cost))
    total = (await session.execute(stmt)).scalar_one()

    assert isinstance(total, Decimal), (
        f"Expected Decimal from SUM(Numeric), got {type(total).__name__}"
    )
    # Two-decimal precision survives the aggregation: the result should equal
    # itself when quantized to two places.
    assert total == total.quantize(Decimal("0.01"))
    # Sanity: seeded fleet has non-trivial total maintenance spend.
    assert total > Decimal("0")


@pytest.mark.asyncio
async def test_sql_groupby_orderby_top_n_truncation_is_stable(
    session: AsyncSession,
) -> None:
    """LIMIT N over a stably-ordered GROUP BY returns the same N twice.

    The .NET pyramid-of-pain test pinned that re-running an aggregated query
    yields the same ranking. Trivially true on SQLAlchemy + aiosqlite, but
    cheap to lock in -- a flaky cursor or a concurrent-write race would
    surface here first.
    """
    stmt = (
        select(MaintenanceRecord.vehicle_id, func.sum(MaintenanceRecord.cost))
        .group_by(MaintenanceRecord.vehicle_id)
        .order_by(
            func.sum(MaintenanceRecord.cost).desc(),
            MaintenanceRecord.vehicle_id.asc(),
        )
        .limit(3)
    )
    first = (await session.execute(stmt)).all()
    second = (await session.execute(stmt)).all()
    assert first == second
    assert len(first) == 3
