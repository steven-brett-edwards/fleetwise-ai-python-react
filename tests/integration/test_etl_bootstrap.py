"""Lifespan-startup ETL hook tests.

Two pinned behaviors:

1. Empty inspections table + the committed CSV corpus = inspections
   loaded at startup. Pinned because this is what the deployed demo
   relies on -- if it regresses, the chat tab can't answer inspection
   questions on the live site.
2. Non-empty inspections table = no-op. Pinned because the function
   should be idempotent across restarts and dev runs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.domain.entities import VehicleInspection
from fleetwise.etl.bootstrap import ingest_inspections_if_empty
from fleetwise.settings import Settings


@pytest.mark.asyncio
async def test_ingest_inspections_if_empty_loads_committed_corpus(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Empty table + corpus on disk -> inspections appear in the DB.

    On CI there's no LLM API key, so the mapper falls back to seeded-only
    matching for non-canonical headers. The two fixture files using fully
    canonical snake_case headers (batch-b + ev-fleet, 13 records combined)
    are guaranteed to load; the rest depend on an LLM call we won't make
    in this environment. Asserting only on the canonical-headers slice
    keeps the test deterministic across CI and local-with-key runs.
    """
    settings = Settings(etl_cache_dir=str(tmp_path), inspections_dir="./data/inspections")
    loaded = await ingest_inspections_if_empty(session, settings)

    assert loaded > 0
    rows = (await session.execute(select(VehicleInspection))).scalars().all()
    sources = {r.source_file for r in rows}
    assert "inspections-2026-03-batch-b.csv" in sources
    assert "ev-fleet-2026-04.csv" in sources


@pytest.mark.asyncio
async def test_ingest_inspections_if_empty_is_noop_when_table_populated(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Pre-existing row -> short-circuit, no run_pipeline call, returns 0."""
    session.add(
        VehicleInspection(
            vehicle_id=None,
            unmatched_asset_number="V-9999-PRIMER",
            inspected_at=datetime(2026, 1, 1),
            inspector_name="primer",
            mileage=100,
            passed=True,
            findings="primer row",
            recommendations=None,
            source_file="primer.csv",
            source_row_hash="primer-hash",
        )
    )
    await session.commit()

    settings = Settings(etl_cache_dir=str(tmp_path), inspections_dir="./data/inspections")
    loaded = await ingest_inspections_if_empty(session, settings)

    assert loaded == 0
    # Still exactly one row -- the primer.
    rows = (await session.execute(select(VehicleInspection))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_ingest_inspections_if_empty_handles_missing_directory(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Misconfigured inspections_dir doesn't crash boot -- returns 0 with a log."""
    settings = Settings(
        etl_cache_dir=str(tmp_path), inspections_dir=str(tmp_path / "does-not-exist")
    )
    loaded = await ingest_inspections_if_empty(session, settings)

    assert loaded == 0


@pytest.mark.asyncio
async def test_ingest_inspections_if_empty_handles_empty_directory(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Empty directory (no CSVs) is also a no-op, distinct from 'missing'."""
    empty_dir = tmp_path / "inspections"
    empty_dir.mkdir()

    settings = Settings(etl_cache_dir=str(tmp_path), inspections_dir=str(empty_dir))
    loaded = await ingest_inspections_if_empty(session, settings)

    assert loaded == 0
