"""Load stage: NormalizedInspection -> VehicleInspection row in the DB.

Resolves ``asset_number`` to a ``vehicle_id`` (or ``None`` for orphans),
upserts via the inspection repository's idempotency key, and returns
``(entity, created)`` so the pipeline can tally per-file metrics.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.repositories import inspection as inspection_repo
from fleetwise.domain.entities import Vehicle, VehicleInspection
from fleetwise.etl.schema import NormalizedInspection


async def _resolve_vehicle_id(session: AsyncSession, asset_number: str) -> int | None:
    """Look up the seeded vehicle by asset number; return ``None`` for orphans."""
    stmt = select(Vehicle.id).where(Vehicle.asset_number == asset_number)
    return (await session.execute(stmt)).scalar_one_or_none()


async def load_row(
    session: AsyncSession, normalized: NormalizedInspection
) -> tuple[VehicleInspection, bool]:
    """Upsert one normalized row. Returns ``(entity, created)``.

    ``created=False`` means the ``(source_file, source_row_hash)`` pair
    already existed -- the idempotency contract. ``created=True`` means a
    new row was inserted.
    """
    vehicle_id = await _resolve_vehicle_id(session, normalized.asset_number)
    candidate = VehicleInspection(
        vehicle_id=vehicle_id,
        unmatched_asset_number=None if vehicle_id is not None else normalized.asset_number,
        inspected_at=normalized.inspected_at,
        inspector_name=normalized.inspector_name,
        mileage=normalized.mileage,
        passed=normalized.passed,
        findings=normalized.findings,
        recommendations=normalized.recommendations,
        source_file=normalized.source_file,
        source_row_hash=normalized.source_row_hash,
    )
    return await inspection_repo.upsert_inspection(session, candidate)
