"""End-to-end pipeline tests against the in-memory engine + seeded fleet.

The session fixture (from tests/conftest.py) provides the seeded fleet
DB. We hand-craft a small temp-dir of inspection CSVs so the test owns
its own fixture data and the assertions are tight.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.domain.entities import VehicleInspection
from fleetwise.etl.pipeline import run_pipeline
from fleetwise.etl.schema import HeaderMapping, HeaderMappingResult
from fleetwise.settings import Settings

# Headers we know the LLM should map for the fixture corpus. Lowercased.
# Used by the corpus-smoke test below to substitute for a real LLM call --
# covers both human-readable variants ("Asset Number") and machine-style
# variants ("unit_no") for every required + optional canonical field.
_FIXTURE_HEADER_LOOKUP: dict[str, str] = {
    # asset_number
    "asset number": "asset_number",
    "vehicle id": "asset_number",
    "asset #": "asset_number",
    "unit_no": "asset_number",
    "vehicle_asset": "asset_number",
    # inspected_at
    "inspection date": "inspected_at",
    "date inspected": "inspected_at",
    "inspection_dt": "inspected_at",
    "inspected_on": "inspected_at",
    "date": "inspected_at",
    # inspector_name
    "inspector": "inspector_name",
    "inspector name": "inspector_name",
    "tech": "inspector_name",
    "inspected_by": "inspector_name",
    # mileage variants where the canonical lower-case match doesn't apply.
    # ("mileage" alone is already a canonical match.)
    "odometer": "mileage",
    "miles": "mileage",
    "current_mileage": "mileage",
    "mileage_reading": "mileage",
    # passed
    "result": "passed",
    "outcome": "passed",
    "passed (y/n)": "passed",
    "pass/fail": "passed",
    # findings -- mostly direct canonical matches, but some files use synonyms.
    "notes": "findings",
    "observations": "findings",
    "comments": "findings",
    # recommendations
    "followup": "recommendations",
    "action items": "recommendations",
    "recommendation": "recommendations",
}


def _no_llm_model() -> MagicMock:
    """A chat model that should never be invoked.

    Used by tests where every CSV uses canonical headers, so the cheap
    path resolves everything without touching the LLM.
    """
    structured = MagicMock()
    structured.invoke.return_value = HeaderMappingResult(mappings=[])
    chat = MagicMock()
    chat.with_structured_output.return_value = structured
    return chat


def _fixture_corpus_chat_model() -> MagicMock:
    """Fake chat that maps headers like a real LLM would for the fixtures.

    Parses the header list out of the prompt body (the mapper formats
    them as ``  - 'header_name'`` lines) and returns a mapping built
    from :data:`_FIXTURE_HEADER_LOOKUP`. Lets the corpus smoke test
    exercise the full pipeline without a provider key.
    """

    def fake_invoke(prompt: str) -> HeaderMappingResult:
        headers = re.findall(r"  - '([^']+)'", prompt)
        mappings = [
            HeaderMapping(
                source=h,
                canonical=_FIXTURE_HEADER_LOOKUP.get(h.strip().lower()),  # type: ignore[arg-type]
            )
            for h in headers
        ]
        return HeaderMappingResult(mappings=mappings)

    structured = MagicMock()
    structured.invoke.side_effect = fake_invoke
    chat = MagicMock()
    chat.with_structured_output.return_value = structured
    return chat


def _write_csv(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


@pytest.mark.asyncio
async def test_pipeline_loads_clean_rows_and_resolves_vehicle_ids(
    session: AsyncSession, tmp_path: Path
) -> None:
    csv = _write_csv(
        tmp_path,
        "clean.csv",
        "asset_number,inspected_at,inspector_name,mileage,passed,findings,recommendations\n"
        "V-2020-0015,2026-03-15,Maria Alvarez,49100,Pass,Brakes 50%.,\n"
        "V-2017-0007,2026-03-15,J. Walters,148210,Fail,"
        "Right rear brake pad below 3mm.,Pull from service.\n",
    )

    report = await run_pipeline(
        session, [csv], model=_no_llm_model(), settings=Settings(etl_cache_dir=str(tmp_path))
    )

    assert report.total_loaded == 2
    assert report.total_skipped == 0
    assert report.total_orphaned == 0
    assert report.total_rejected == 0

    rows = (await session.execute(select(VehicleInspection))).scalars().all()
    assert len(rows) == 2
    assert all(r.vehicle_id is not None for r in rows)


@pytest.mark.asyncio
async def test_pipeline_flags_orphans_without_dropping_them(
    session: AsyncSession, tmp_path: Path
) -> None:
    csv = _write_csv(
        tmp_path,
        "orphan.csv",
        "asset_number,inspected_at,inspector_name,mileage,passed,findings\n"
        "V-9999-0001,2026-02-12,K. Nguyen,12000,OK,Mystery vehicle in lot.\n"
        "V-2020-0015,2026-02-12,K. Nguyen,49000,OK,Routine.\n",
    )

    report = await run_pipeline(
        session, [csv], model=_no_llm_model(), settings=Settings(etl_cache_dir=str(tmp_path))
    )

    assert report.total_loaded == 2
    assert report.total_orphaned == 1

    orphan = (
        await session.execute(
            select(VehicleInspection).where(VehicleInspection.vehicle_id.is_(None))
        )
    ).scalar_one()
    assert orphan.unmatched_asset_number == "V-9999-0001"


@pytest.mark.asyncio
async def test_pipeline_is_idempotent_on_rerun(session: AsyncSession, tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path,
        "rerun.csv",
        "asset_number,inspected_at,inspector_name,mileage,passed,findings\n"
        "V-2020-0015,2026-03-15,Maria Alvarez,49100,Pass,Brakes 50%.\n",
    )

    settings = Settings(etl_cache_dir=str(tmp_path))
    first = await run_pipeline(session, [csv], model=_no_llm_model(), settings=settings)
    second = await run_pipeline(session, [csv], model=_no_llm_model(), settings=settings)

    assert first.total_loaded == 1
    assert second.total_loaded == 0
    assert second.total_skipped == 1

    # Still exactly one row in the table.
    count = len((await session.execute(select(VehicleInspection))).scalars().all())
    assert count == 1


@pytest.mark.asyncio
async def test_pipeline_rejects_rows_with_unparseable_values(
    session: AsyncSession, tmp_path: Path
) -> None:
    csv = _write_csv(
        tmp_path,
        "bad-mileage.csv",
        "asset_number,inspected_at,inspector_name,mileage,passed,findings\n"
        "V-2020-0015,2026-03-15,Maria Alvarez,not-a-number,Pass,Routine.\n"
        "V-2017-0007,2026-03-15,J. Walters,148210,Pass,Routine.\n",
    )

    report = await run_pipeline(
        session, [csv], model=_no_llm_model(), settings=Settings(etl_cache_dir=str(tmp_path))
    )

    assert report.total_loaded == 1
    assert len(report.files[0].rows_rejected) == 1
    rejected_idx, reason = report.files[0].rows_rejected[0]
    assert rejected_idx == 0
    assert "mileage" in reason


@pytest.mark.asyncio
async def test_pipeline_rejects_every_row_when_required_header_unmappable(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Missing-required-headers branch: bulk-rejects every row, doesn't crash."""
    csv = _write_csv(
        tmp_path,
        "no-asset.csv",
        # Missing the asset_number column entirely; rows can't be loaded.
        "inspected_at,inspector_name,mileage,passed,findings\n"
        "2026-03-15,Maria Alvarez,49100,Pass,Routine.\n",
    )

    report = await run_pipeline(
        session, [csv], model=_no_llm_model(), settings=Settings(etl_cache_dir=str(tmp_path))
    )

    assert report.total_loaded == 0
    assert report.total_rejected == 1
    assert "missing required mapped headers" in report.files[0].rows_rejected[0][1]


@pytest.mark.asyncio
async def test_pipeline_handles_empty_csv_without_crashing(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Empty-headers branch: zero-byte CSV produces an empty FileReport."""
    csv = _write_csv(tmp_path, "empty.csv", "")

    report = await run_pipeline(
        session, [csv], model=_no_llm_model(), settings=Settings(etl_cache_dir=str(tmp_path))
    )

    assert len(report.files) == 1
    assert report.files[0].rows_total == 0
    assert report.total_loaded == 0


@pytest.mark.asyncio
async def test_pipeline_skips_blank_lines_silently(session: AsyncSession, tmp_path: Path) -> None:
    """Blank lines in a CSV shouldn't count as either rejected or loaded."""
    csv = _write_csv(
        tmp_path,
        "with-blanks.csv",
        "asset_number,inspected_at,inspector_name,mileage,passed,findings\n"
        "V-2020-0015,2026-03-15,Maria Alvarez,49100,Pass,Routine.\n"
        ",,,,,\n"
        "V-2017-0007,2026-03-15,J. Walters,148210,Pass,Routine.\n",
    )

    report = await run_pipeline(
        session, [csv], model=_no_llm_model(), settings=Settings(etl_cache_dir=str(tmp_path))
    )

    assert report.total_loaded == 2
    assert report.total_rejected == 0


@pytest.mark.asyncio
async def test_pipeline_handles_committed_fixture_corpus(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Smoke test the actual data/inspections corpus end-to-end."""
    inspections_dir = Path(__file__).resolve().parents[2] / "data" / "inspections"
    csvs = sorted(inspections_dir.glob("*.csv"))
    assert len(csvs) >= 10, "expected at least 10 inspection fixtures"

    report = await run_pipeline(
        session,
        csvs,
        model=_fixture_corpus_chat_model(),
        settings=Settings(etl_cache_dir=str(tmp_path)),
    )

    # All 12 files should produce some output. None should reject 100%
    # of their rows -- if any do, the canonical mapping or coercers
    # have regressed.
    for f in report.files:
        assert f.rows_total > 0, f"{f.path}: zero rows"
        assert len(f.rows_rejected) < f.rows_total, (
            f"{f.path}: every row rejected -- {f.rows_rejected[:3]}"
        )

    # Three orphans across the corpus, all V-9999-0001.
    assert report.total_orphaned == 3
    orphans = (
        (
            await session.execute(
                select(VehicleInspection).where(VehicleInspection.vehicle_id.is_(None))
            )
        )
        .scalars()
        .all()
    )
    assert all(o.unmatched_asset_number == "V-9999-0001" for o in orphans)
