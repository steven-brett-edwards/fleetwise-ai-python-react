"""Vehicles router -- parity with .NET `VehiclesController`.

Route-ordering note: `GET /summary` is declared before `GET /{id:int}` so
FastAPI's path-matcher takes the literal before the typed param. Same
convention the .NET controller relies on.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from fleetwise.api.deps import SessionDep
from fleetwise.data.repositories import (
    maintenance as maintenance_repo,
    vehicle as vehicle_repo,
    work_order as work_order_repo,
)
from fleetwise.domain.dto import (
    FleetSummaryResponse,
    MaintenanceRecordResponse,
    VehicleResponse,
    WorkOrderResponse,
)
from fleetwise.domain.enums import FuelType, VehicleStatus

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleResponse])
async def list_vehicles(
    session: SessionDep,
    status: VehicleStatus | None = None,
    department: str | None = None,
    fuel_type: FuelType | None = None,
) -> list[VehicleResponse]:
    vehicles = await vehicle_repo.get_all(
        session, status=status, department=department, fuel_type=fuel_type
    )
    return [VehicleResponse.model_validate(v) for v in vehicles]


@router.get("/summary", response_model=FleetSummaryResponse)
async def fleet_summary(session: SessionDep) -> FleetSummaryResponse:
    summary = await vehicle_repo.get_fleet_summary(session)
    return FleetSummaryResponse.model_validate(summary)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(vehicle_id: int, session: SessionDep) -> VehicleResponse:
    vehicle = await vehicle_repo.get_by_id(session, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404)
    return VehicleResponse.model_validate(vehicle)


@router.get("/{vehicle_id}/maintenance", response_model=list[MaintenanceRecordResponse])
async def vehicle_maintenance(
    vehicle_id: int, session: SessionDep
) -> list[MaintenanceRecordResponse]:
    vehicle = await vehicle_repo.get_by_id(session, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404)
    records = await maintenance_repo.get_by_vehicle_id(session, vehicle_id=vehicle_id)
    return [MaintenanceRecordResponse.model_validate(r) for r in records]


@router.get("/{vehicle_id}/work-orders", response_model=list[WorkOrderResponse])
async def vehicle_work_orders(vehicle_id: int, session: SessionDep) -> list[WorkOrderResponse]:
    vehicle = await vehicle_repo.get_by_id(session, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404)
    work_orders = await work_order_repo.get_by_vehicle_id(session, vehicle_id=vehicle_id)
    return [WorkOrderResponse.model_validate(wo) for wo in work_orders]
