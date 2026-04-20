"""Maintenance router -- parity with .NET `MaintenanceController`.

Both endpoints flatten the eagerly-loaded `Vehicle` into sibling fields on
the response, matching the anonymous projection the .NET controller emits.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from fleetwise.api.deps import SessionDep
from fleetwise.data.repositories import maintenance as maintenance_repo
from fleetwise.domain.dto import MaintenanceScheduleItemResponse
from fleetwise.domain.entities import MaintenanceSchedule

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _project(schedule: MaintenanceSchedule) -> MaintenanceScheduleItemResponse:
    """Flatten Vehicle nav properties onto the schedule response."""
    vehicle = schedule.vehicle
    return MaintenanceScheduleItemResponse(
        id=schedule.id,
        vehicle_id=schedule.vehicle_id,
        vehicle_asset_number=vehicle.asset_number,
        vehicle_description=f"{vehicle.year} {vehicle.make} {vehicle.model}",
        maintenance_type=schedule.maintenance_type,
        next_due_date=schedule.next_due_date,
        next_due_mileage=schedule.next_due_mileage,
        current_mileage=vehicle.current_mileage,
        last_completed_date=schedule.last_completed_date,
        last_completed_mileage=schedule.last_completed_mileage,
    )


@router.get("/overdue", response_model=list[MaintenanceScheduleItemResponse])
async def overdue(session: SessionDep) -> list[MaintenanceScheduleItemResponse]:
    schedules = await maintenance_repo.get_overdue_schedules(session)
    return [_project(s) for s in schedules]


@router.get("/upcoming", response_model=list[MaintenanceScheduleItemResponse])
async def upcoming(
    session: SessionDep,
    days: int = Query(30, ge=0),
    miles: int = Query(5000, ge=0),
) -> list[MaintenanceScheduleItemResponse]:
    schedules = await maintenance_repo.get_upcoming_schedules(
        session, within_days=days, within_miles=miles
    )
    return [_project(s) for s in schedules]
