"""VehicleInspection repository -- ETL load target + read access for the chat tool.

Two-and-a-half methods:

- :func:`upsert_inspection` is the load-side contract. It looks up the
  ``(source_file, source_row_hash)`` unique index; on a hit it returns
  the existing row with ``created=False`` (no DB write), making the ETL
  pipeline idempotent. On a miss it inserts and returns ``created=True``.
- :func:`get_recent_for_asset_number` powers the new chat tool. Joins
  through ``Vehicle.asset_number`` and falls back to
  ``unmatched_asset_number`` so a recruiter asking about an orphaned
  asset still gets *some* answer ("we have N inspections on file but
  the asset is not in the fleet roster") rather than a silent zero.
- :func:`get_recent_for_vehicle` is the by-id variant -- handier for
  callers that already resolved the Vehicle.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.domain.entities import Vehicle, VehicleInspection


async def upsert_inspection(
    session: AsyncSession, candidate: VehicleInspection
) -> tuple[VehicleInspection, bool]:
    """Insert if (source_file, source_row_hash) is new; otherwise return existing.

    Caller owns the commit -- mirrors the seed module's pattern of staging
    everything in one session and committing at the pipeline boundary.
    """
    stmt = select(VehicleInspection).where(
        VehicleInspection.source_file == candidate.source_file,
        VehicleInspection.source_row_hash == candidate.source_row_hash,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False
    session.add(candidate)
    await session.flush()
    return candidate, True


async def get_recent_for_vehicle(
    session: AsyncSession, vehicle_id: int, limit: int = 5
) -> list[VehicleInspection]:
    """Most recent inspections for a known vehicle, newest first."""
    stmt = (
        select(VehicleInspection)
        .where(VehicleInspection.vehicle_id == vehicle_id)
        .order_by(VehicleInspection.inspected_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_recent_for_asset_number(
    session: AsyncSession, asset_number: str, limit: int = 5
) -> list[VehicleInspection]:
    """Most recent inspections for an asset number, including orphan rows.

    Resolves the asset number two ways:

    1. Joins to Vehicle for the matched-FK case (the normal path).
    2. Falls back to ``unmatched_asset_number`` for orphan rows, so a
       lookup of ``V-9999-0001`` still surfaces the inspections the
       pipeline preserved for it.

    Returns at most ``limit`` rows total across both paths, newest first.
    """
    stmt = (
        select(VehicleInspection)
        .outerjoin(Vehicle, VehicleInspection.vehicle_id == Vehicle.id)
        .where(
            or_(
                Vehicle.asset_number == asset_number,
                VehicleInspection.unmatched_asset_number == asset_number,
            )
        )
        .order_by(VehicleInspection.inspected_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
