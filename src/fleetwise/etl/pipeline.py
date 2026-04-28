"""Pipeline orchestrator: glob -> extract -> map -> transform -> load -> report.

The orchestrator is the only stage that owns a session. Inner stages are
pure (extract / map / transform) or take a session as a parameter (load).
That separation makes each stage independently testable and keeps the
pipeline's commit boundary unambiguous: one commit per file, after every
row has been attempted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.etl.extract import read_csv
from fleetwise.etl.load import load_row
from fleetwise.etl.mapper import map_headers
from fleetwise.etl.schema import REQUIRED_CANONICAL
from fleetwise.etl.transform import RowTransformError, transform_row
from fleetwise.settings import Settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


@dataclass
class FileReport:
    """Per-file ETL outcome. Surfaced verbatim in CLI output and JSON dumps."""

    path: str
    rows_total: int = 0
    rows_loaded: int = 0
    rows_skipped_existing: int = 0
    rows_orphaned: int = 0
    rows_rejected: list[tuple[int, str]] = field(default_factory=list)
    header_mapping: dict[str, str | None] = field(default_factory=dict)


@dataclass
class IngestReport:
    """Aggregate report across all files in one ingest invocation."""

    files: list[FileReport] = field(default_factory=list)

    @property
    def total_loaded(self) -> int:
        return sum(f.rows_loaded for f in self.files)

    @property
    def total_skipped(self) -> int:
        return sum(f.rows_skipped_existing for f in self.files)

    @property
    def total_orphaned(self) -> int:
        return sum(f.rows_orphaned for f in self.files)

    @property
    def total_rejected(self) -> int:
        return sum(len(f.rows_rejected) for f in self.files)


async def run_pipeline(
    session: AsyncSession,
    paths: list[Path],
    *,
    model: BaseChatModel | None = None,
    settings: Settings | None = None,
) -> IngestReport:
    """Ingest every file in ``paths``. One commit per file at the boundary.

    ``model`` is an optional LangChain chat model passed through to the
    header mapper -- tests inject a fake; production uses the provider
    factory's default. ``settings`` overrides the global Settings (mainly
    so tests can route the header-mapping cache to a tmp_path instead of
    polluting ``./data/etl-cache``).
    """
    report = IngestReport()
    for path in paths:
        file_report = await _ingest_file(session, path, model=model, settings=settings)
        report.files.append(file_report)
        await session.commit()
    return report


async def _ingest_file(
    session: AsyncSession,
    path: Path,
    *,
    model: BaseChatModel | None,
    settings: Settings | None,
) -> FileReport:
    headers, rows = read_csv(path)
    report = FileReport(path=str(path))
    if not headers:
        return report

    mapping = map_headers(headers, model=model, settings=settings)
    report.header_mapping = mapping
    report.rows_total = len(rows)

    # Required-field guard. If any required canonical name didn't get
    # mapped, every row is rejected with the same reason -- spend the row
    # budget once, not row-by-row, and surface it loudly so the operator
    # knows it's a header problem, not a value problem.
    missing_required = [
        canonical for canonical in REQUIRED_CANONICAL if canonical not in set(mapping.values())
    ]
    if missing_required:
        for i, _row in enumerate(rows):
            report.rows_rejected.append((i, f"missing required mapped headers: {missing_required}"))
        return report

    # Index map: canonical -> column position in the row.
    canonical_to_idx: dict[str, int] = {}
    for idx, header in enumerate(headers):
        canonical = mapping.get(header)
        if canonical is not None:
            canonical_to_idx[canonical] = idx

    for row_idx, raw in enumerate(rows):
        if not any((cell or "").strip() for cell in raw):
            # Skip blank lines silently -- a real-world quirk of CSVs.
            report.rows_total -= 1
            continue
        try:
            mapped: dict[str, str | None] = {}
            for canonical, idx in canonical_to_idx.items():
                mapped[canonical] = raw[idx] if idx < len(raw) else None
            normalized = transform_row(mapped, source_file=path.name)
        except RowTransformError as exc:
            report.rows_rejected.append((row_idx, str(exc)))
            continue

        _entity, created = await load_row(session, normalized)
        if created:
            report.rows_loaded += 1
            if _entity.vehicle_id is None:
                report.rows_orphaned += 1
        else:
            report.rows_skipped_existing += 1

    return report
