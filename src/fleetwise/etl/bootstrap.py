"""Startup-time inspection ingest -- the deployed-demo's entry point.

Mirrors the shape of ``fleetwise.data.seed.seed_if_empty``: the FastAPI
lifespan calls :func:`ingest_inspections_if_empty` at boot, the function
no-ops if the table already has rows, otherwise it walks
``settings.inspections_dir`` and runs :func:`fleetwise.etl.pipeline.run_pipeline`
against the committed CSV corpus.

Why this exists despite the original Phase 10 plan punting on it:
Render's free tier has an ephemeral filesystem, so the inspection table
evaporates on every cold-start. Without a startup hook, the deployed
demo would 0-match every "show me the latest inspection on V-2020-0015"
question -- a real demo gap. The CLI is still the canonical way to run
the pipeline (and the docs lead with it), but the lifespan hook is what
keeps the live demo self-contained.

Errors during ingest are caught and logged. A failure to ingest must
never tank the API boot -- the rest of the demo works without inspection
data, and a recruiter staring at a 502 is worse than a recruiter who
gets "No inspections found" for one question.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.domain.entities import VehicleInspection
from fleetwise.etl.pipeline import run_pipeline
from fleetwise.settings import Settings, get_settings

logger = logging.getLogger(__name__)


async def ingest_inspections_if_empty(
    session: AsyncSession, settings: Settings | None = None
) -> int:
    """Auto-load the fixture CSVs at startup. Returns rows loaded (0 on no-op).

    No-ops if the inspections table already has at least one row -- handy
    locally where the dev DB persists across runs, and idempotent on Render
    where the volume is ephemeral but the function is still safe to call.
    """
    settings = settings or get_settings()

    existing = (await session.execute(select(VehicleInspection.id).limit(1))).scalar_one_or_none()
    if existing is not None:
        logger.info("vehicle_inspections is non-empty; skipping startup ingest")
        return 0

    inspections_dir = Path(settings.inspections_dir)
    if not inspections_dir.is_dir():
        logger.warning("inspections_dir %s does not exist; nothing to ingest", inspections_dir)
        return 0

    csvs = sorted(inspections_dir.glob("*.csv"))
    if not csvs:
        logger.info("No CSVs in %s; skipping startup ingest", inspections_dir)
        return 0

    try:
        report = await run_pipeline(session, csvs, settings=settings)
    except Exception:
        logger.exception("Startup inspection ingest failed; continuing without inspections")
        return 0

    logger.info(
        "Startup inspection ingest: %d loaded, %d orphaned, %d rejected across %d files",
        report.total_loaded,
        report.total_orphaned,
        report.total_rejected,
        len(report.files),
    )
    return report.total_loaded
