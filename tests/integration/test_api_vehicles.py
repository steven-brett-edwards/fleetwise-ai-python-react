"""Integration tests for the vehicles router.

Exercises the full FastAPI stack against the seeded in-memory DB via the
shared `client` fixture. We check status codes, wire-format (PascalCase
keys, numeric Decimals), filter combinations, and the route-ordering
contract that puts `/summary` ahead of `/{vehicle_id}`.
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_list_vehicles_returns_seeded_fleet(
    client: AsyncClient, expected_seed_counts: dict[str, int]
) -> None:
    response = await client.get("/api/vehicles")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == expected_seed_counts["vehicles"]

    sample = body[0]
    # PascalCase on the wire, ordered by asset number (matches repo contract).
    assert "AssetNumber" in sample
    assert "FuelType" in sample
    assert "CurrentMileage" in sample
    asset_numbers = [v["AssetNumber"] for v in body]
    assert asset_numbers == sorted(asset_numbers)


async def test_list_vehicles_filters_compose(client: AsyncClient) -> None:
    # Filter on status + fuel type simultaneously.
    r_all = await client.get("/api/vehicles")
    r_filtered = await client.get("/api/vehicles?status=Active&fuel_type=Diesel")
    assert r_filtered.status_code == 200
    filtered = r_filtered.json()
    assert len(filtered) <= len(r_all.json())
    assert all(v["Status"] == "Active" and v["FuelType"] == "Diesel" for v in filtered)


async def test_get_vehicle_by_id_roundtrips_decimal_as_number(client: AsyncClient) -> None:
    response = await client.get("/api/vehicles/1")
    assert response.status_code == 200
    body = response.json()
    assert body["Id"] == 1
    # Decimal serializes as a JSON number (float), not a string -- .NET parity.
    assert isinstance(body["AcquisitionCost"], int | float)


async def test_get_vehicle_by_id_returns_404_for_unknown(client: AsyncClient) -> None:
    response = await client.get("/api/vehicles/99999")
    assert response.status_code == 404


async def test_summary_route_precedes_id_route(client: AsyncClient) -> None:
    """`GET /vehicles/summary` must be routed to the summary handler, not
    `GET /vehicles/{id}` with id="summary" (which would 422)."""
    response = await client.get("/api/vehicles/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["TotalVehicles"] == 35
    # The three group-by dicts come back populated.
    assert body["ByStatus"] and body["ByFuelType"] and body["ByDepartment"]


async def test_vehicle_maintenance_history(client: AsyncClient) -> None:
    response = await client.get("/api/vehicles/1/maintenance")
    assert response.status_code == 200
    records = response.json()
    assert records, "vehicle 1 should have maintenance records"
    assert all(r["VehicleId"] == 1 for r in records)
    # Costs serialize as numbers.
    assert all(isinstance(r["Cost"], int | float) for r in records)


async def test_vehicle_maintenance_history_404_for_unknown(client: AsyncClient) -> None:
    response = await client.get("/api/vehicles/99999/maintenance")
    assert response.status_code == 404


async def test_vehicle_work_orders(client: AsyncClient) -> None:
    response = await client.get("/api/vehicles/1/work-orders")
    assert response.status_code == 200
    work_orders = response.json()
    assert all(wo["VehicleId"] == 1 for wo in work_orders)


async def test_vehicle_work_orders_404_for_unknown(client: AsyncClient) -> None:
    response = await client.get("/api/vehicles/99999/work-orders")
    assert response.status_code == 404
