"""Tool-layer tests for `ai.tools.inspection`."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from fleetwise.ai.tools.inspection import get_recent_inspections
from fleetwise.domain.entities import Vehicle, VehicleInspection

pytestmark = pytest.mark.usefixtures("tool_session_factory")


async def _seed_inspections(factory: async_sessionmaker, *inspections: VehicleInspection) -> None:
    async with factory() as session:
        session.add_all(inspections)
        await session.commit()


async def test_get_recent_inspections_returns_no_data_message_when_none(
    tool_session_factory: async_sessionmaker,
) -> None:
    out = await get_recent_inspections.ainvoke({"asset_number": "V-2020-0015"})
    assert "No inspections found" in out


async def test_get_recent_inspections_for_seeded_vehicle(
    tool_session_factory: async_sessionmaker,
) -> None:
    # V-2020-0015 is seeded -- look up its DB id first so we can attach.
    async with tool_session_factory() as session:
        v_id = (
            await session.execute(select(Vehicle.id).where(Vehicle.asset_number == "V-2020-0015"))
        ).scalar_one()

    await _seed_inspections(
        tool_session_factory,
        VehicleInspection(
            vehicle_id=v_id,
            unmatched_asset_number=None,
            inspected_at=datetime(2026, 3, 15),
            inspector_name="Maria Alvarez",
            mileage=49100,
            passed=True,
            findings="Brakes 50%; routine.",
            recommendations=None,
            source_file="batch-a.csv",
            source_row_hash="hash-1",
        ),
        VehicleInspection(
            vehicle_id=v_id,
            unmatched_asset_number=None,
            inspected_at=datetime(2026, 1, 8),
            inspector_name="Maria Alvarez",
            mileage=48200,
            passed=True,
            findings="Approaching 50k service threshold.",
            recommendations="Book 50k service.",
            source_file="jan-2026.csv",
            source_row_hash="hash-2",
        ),
    )

    out = await get_recent_inspections.ainvoke({"asset_number": "V-2020-0015"})

    assert "Found 2 inspection(s) for V-2020-0015:" in out
    # Newest first
    assert out.index("Brakes 50%") < out.index("50k service threshold")
    # No orphan flag on either record.
    assert '"Orphan": false' in out
    assert '"Orphan": true' not in out


async def test_get_recent_inspections_surfaces_orphan_with_flag(
    tool_session_factory: async_sessionmaker,
) -> None:
    """An asset number not in the seeded fleet still resolves through unmatched_asset_number."""
    await _seed_inspections(
        tool_session_factory,
        VehicleInspection(
            vehicle_id=None,
            unmatched_asset_number="V-9999-0001",
            inspected_at=datetime(2026, 2, 12),
            inspector_name="K. Nguyen",
            mileage=12000,
            passed=True,
            findings="Mystery vehicle in lot.",
            recommendations=None,
            source_file="water-dept-feb-2026.csv",
            source_row_hash="hash-orphan",
        ),
    )

    out = await get_recent_inspections.ainvoke({"asset_number": "V-9999-0001"})
    assert "Found 1 inspection(s) for V-9999-0001:" in out
    assert '"Orphan": true' in out


async def test_get_recent_inspections_respects_limit(
    tool_session_factory: async_sessionmaker,
) -> None:
    async with tool_session_factory() as session:
        v_id = (
            await session.execute(select(Vehicle.id).where(Vehicle.asset_number == "V-2020-0015"))
        ).scalar_one()

    await _seed_inspections(
        tool_session_factory,
        *[
            VehicleInspection(
                vehicle_id=v_id,
                unmatched_asset_number=None,
                inspected_at=datetime(2026, i, 1),
                inspector_name="M. A.",
                mileage=49000 + i,
                passed=True,
                findings=f"Inspection {i}",
                recommendations=None,
                source_file="x.csv",
                source_row_hash=f"hash-{i}",
            )
            for i in range(1, 8)
        ],
    )

    out = await get_recent_inspections.ainvoke({"asset_number": "V-2020-0015", "limit": 3})
    assert "Found 3 inspection(s) for V-2020-0015:" in out
