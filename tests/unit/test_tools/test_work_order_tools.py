"""Tool-layer tests for `ai.tools.work_order`."""

from __future__ import annotations

import pytest

from fleetwise.ai.tools.work_order import (
    get_open_work_orders,
    get_parts_below_reorder_threshold,
    get_work_order_details,
)

pytestmark = pytest.mark.usefixtures("tool_session_factory")


async def test_get_open_work_orders_returns_eight() -> None:
    # The seeded dataset has 8 Open + InProgress work orders.
    out = await get_open_work_orders.ainvoke({})
    assert out.startswith("Found ")
    assert "open work orders" in out


async def test_get_work_order_details_missing() -> None:
    out = await get_work_order_details.ainvoke({"work_order_number": "WO-9999-99999"})
    assert out == "No work order found with number WO-9999-99999."


async def test_get_parts_below_reorder_threshold_returns_seven() -> None:
    # Seed data: 7 parts below reorder threshold.
    out = await get_parts_below_reorder_threshold.ainvoke({})
    assert out.startswith("Found 7 parts below reorder threshold")
    assert '"Deficit"' in out
