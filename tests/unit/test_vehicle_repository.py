"""Vehicle repository tests.

Exercise every filter on `get_all` and `search`, plus the aggregation
paths (`get_fleet_summary`, `get_vehicles_by_maintenance_cost`). The
fleet-summary test doubles as a regression gate for any enum-value drift
between Python and the .NET dump.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.repositories import vehicle as vehicle_repo
from fleetwise.domain.enums import FuelType, VehicleStatus


async def test_get_all_returns_all_vehicles_ordered_by_asset_number(
    session: AsyncSession,
) -> None:
    vehicles = await vehicle_repo.get_all(session)
    assert len(vehicles) == 35
    assert vehicles == sorted(vehicles, key=lambda v: v.asset_number)


async def test_get_all_filters_by_status(session: AsyncSession) -> None:
    active = await vehicle_repo.get_all(session, status=VehicleStatus.ACTIVE)
    assert active, "seed should contain at least one active vehicle"
    assert all(v.status is VehicleStatus.ACTIVE for v in active)


async def test_get_all_filters_by_department(session: AsyncSession) -> None:
    pw = await vehicle_repo.get_all(session, department="Public Works")
    assert pw, "seed should contain Public Works vehicles"
    assert all(v.department == "Public Works" for v in pw)


async def test_get_all_filters_by_fuel_type(session: AsyncSession) -> None:
    diesel = await vehicle_repo.get_all(session, fuel_type=FuelType.DIESEL)
    assert diesel, "seed should contain diesel vehicles"
    assert all(v.fuel_type is FuelType.DIESEL for v in diesel)


async def test_get_by_id_returns_vehicle_when_present(session: AsyncSession) -> None:
    vehicle = await vehicle_repo.get_by_id(session, 1)
    assert vehicle is not None
    assert vehicle.asset_number == "V-2019-0001"


async def test_get_by_id_returns_none_when_missing(session: AsyncSession) -> None:
    assert await vehicle_repo.get_by_id(session, 99_999) is None


async def test_get_by_asset_number_case_sensitive(session: AsyncSession) -> None:
    assert await vehicle_repo.get_by_asset_number(session, "V-2019-0001") is not None
    # Asset numbers are canonical uppercase; a lowercased lookup is a miss.
    assert await vehicle_repo.get_by_asset_number(session, "v-2019-0001") is None


async def test_search_matches_make_case_insensitively(session: AsyncSession) -> None:
    fords = await vehicle_repo.search(session, make="ford")
    assert fords, "seed should contain Ford vehicles"
    assert all("ford" in v.make.lower() for v in fords)


async def test_search_combines_filters(session: AsyncSession) -> None:
    results = await vehicle_repo.search(
        session, make="ford", status=VehicleStatus.ACTIVE, fuel_type=FuelType.GASOLINE
    )
    for v in results:
        assert "ford" in v.make.lower()
        assert v.status is VehicleStatus.ACTIVE
        assert v.fuel_type is FuelType.GASOLINE


async def test_fleet_summary_totals_and_breakdowns(session: AsyncSession) -> None:
    summary = await vehicle_repo.get_fleet_summary(session)
    assert summary.total_vehicles == 35
    assert sum(summary.by_status.values()) == 35
    assert sum(summary.by_fuel_type.values()) == 35
    assert sum(summary.by_department.values()) == 35
    # Keys are the PascalCase enum values -- matches the .NET wire format.
    assert "Active" in summary.by_status


async def test_top_vehicles_by_maintenance_cost_returns_ranked_list(
    session: AsyncSession,
) -> None:
    top = await vehicle_repo.get_vehicles_by_maintenance_cost(session, top_n=5)
    assert len(top) == 5
    # Costs should be non-increasing.
    assert [x.total_maintenance_cost for x in top] == sorted(
        (x.total_maintenance_cost for x in top), reverse=True
    )
    assert all(x.total_maintenance_cost > Decimal(0) for x in top)
    assert all(x.record_count > 0 for x in top)


async def test_top_vehicles_by_maintenance_cost_respects_top_n(session: AsyncSession) -> None:
    assert len(await vehicle_repo.get_vehicles_by_maintenance_cost(session, top_n=0)) == 0
    assert len(await vehicle_repo.get_vehicles_by_maintenance_cost(session, top_n=1)) == 1
