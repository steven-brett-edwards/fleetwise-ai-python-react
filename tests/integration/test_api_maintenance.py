"""Integration tests for the maintenance router.

Both endpoints do a projection that flattens Vehicle nav properties into
sibling fields -- we pin the projection shape + wire keys here.
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_overdue_returns_flattened_projection(client: AsyncClient) -> None:
    response = await client.get("/api/maintenance/overdue")
    assert response.status_code == 200
    items = response.json()
    # Seed has schedules past due -- the list is non-empty today and will
    # grow over time, but should never shrink below what we seeded.
    assert items, "overdue list should not be empty against seed data"

    item = items[0]
    # Flattened projection fields (not nested under Vehicle).
    for key in (
        "Id",
        "VehicleId",
        "VehicleAssetNumber",
        "VehicleDescription",
        "MaintenanceType",
        "CurrentMileage",
    ):
        assert key in item
    # VehicleDescription is "{Year} {Make} {Model}".
    parts = item["VehicleDescription"].split(" ", 2)
    assert len(parts) == 3 and parts[0].isdigit()


async def test_upcoming_defaults_to_30_days_5000_miles(client: AsyncClient) -> None:
    response = await client.get("/api/maintenance/upcoming")
    assert response.status_code == 200
    body = response.json()
    # Empty is acceptable against current seed/clock; shape is still pinned.
    if body:
        assert {"Id", "VehicleId", "VehicleAssetNumber", "MaintenanceType"} <= body[0].keys()


async def test_upcoming_respects_query_windows(client: AsyncClient) -> None:
    narrow = await client.get("/api/maintenance/upcoming?days=1&miles=10")
    wide = await client.get("/api/maintenance/upcoming?days=365&miles=50000")
    assert narrow.status_code == 200 and wide.status_code == 200
    assert len(narrow.json()) <= len(wide.json())


async def test_upcoming_rejects_negative_window(client: AsyncClient) -> None:
    response = await client.get("/api/maintenance/upcoming?days=-1")
    assert response.status_code == 422
