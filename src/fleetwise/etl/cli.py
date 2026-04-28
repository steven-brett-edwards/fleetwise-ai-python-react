"""``fleetwise-etl`` command-line entrypoint.

Two flags worth knowing:

- ``--json`` dumps the structured ``IngestReport`` to stdout instead of
  the human-readable summary. Used by the integration test and by
  scripted callers that want to act on the metrics.
- ``--db-url`` overrides the configured database. Defaults to whatever
  :func:`fleetwise.settings.get_settings` returns. Useful for one-shot
  runs against a sibling DB file without exporting env vars.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import glob
import json
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fleetwise.domain.entities import Base
from fleetwise.etl.pipeline import IngestReport, run_pipeline
from fleetwise.settings import get_settings


def _expand_paths(args: list[str]) -> list[Path]:
    """Resolve each arg as either a literal path or a glob pattern.

    Uses stdlib ``glob.glob`` because ``Path.glob`` refuses absolute
    patterns -- an annoying papercut when CLI users pass things like
    ``/tmp/inspections/*.csv``.
    """
    out: list[Path] = []
    seen: set[Path] = set()
    for arg in args:
        p = Path(arg)
        if p.exists() and p.is_file():
            if p not in seen:
                out.append(p)
                seen.add(p)
            continue
        for match_str in sorted(glob.glob(arg)):
            match = Path(match_str)
            if match.is_file() and match not in seen:
                out.append(match)
                seen.add(match)
    return out


def _print_human(report: IngestReport) -> None:
    print("ETL ingest report")
    print("=" * 64)
    for f in report.files:
        print(f"\n{f.path}")
        print(f"  rows total       : {f.rows_total}")
        print(f"  rows loaded      : {f.rows_loaded}")
        print(f"  rows skipped     : {f.rows_skipped_existing}  (already in DB)")
        print(f"  rows orphaned    : {f.rows_orphaned}")
        print(f"  rows rejected    : {len(f.rows_rejected)}")
        if f.rows_rejected:
            for idx, reason in f.rows_rejected[:5]:
                print(f"    - row {idx}: {reason}")
            if len(f.rows_rejected) > 5:
                print(f"    ... +{len(f.rows_rejected) - 5} more")
        unmapped = [h for h, c in f.header_mapping.items() if c is None]
        if unmapped:
            print(f"  unmapped headers : {unmapped}")
    print("=" * 64)
    print(
        f"Totals: loaded={report.total_loaded}, "
        f"skipped={report.total_skipped}, "
        f"orphaned={report.total_orphaned}, "
        f"rejected={report.total_rejected}"
    )


def _print_json(report: IngestReport) -> None:
    payload = {
        "files": [dataclasses.asdict(f) for f in report.files],
        "totals": {
            "loaded": report.total_loaded,
            "skipped": report.total_skipped,
            "orphaned": report.total_orphaned,
            "rejected": report.total_rejected,
        },
    }
    print(json.dumps(payload, indent=2, default=str))


async def _run(paths: list[Path], db_url: str | None) -> IngestReport:
    settings = get_settings()
    url = db_url or settings.database_url
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        # `create_all` is idempotent and matches the seed-time pattern; the
        # ETL CLI may run before the API has booted, so we can't rely on
        # the FastAPI lifespan to have created the table.
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            return await run_pipeline(session, paths)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleetwise-etl")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest one or more inspection CSVs.")
    ingest.add_argument("paths", nargs="+", help="CSV file paths or glob patterns.")
    ingest.add_argument("--json", action="store_true", help="Emit IngestReport as JSON.")
    ingest.add_argument(
        "--db-url",
        default=None,
        help="Override the configured DATABASE_URL for this run.",
    )

    args = parser.parse_args(argv)
    if args.command != "ingest":
        parser.print_help()
        return 2

    paths = _expand_paths(args.paths)
    if not paths:
        print("No matching files.", file=sys.stderr)
        return 1

    report = asyncio.run(_run(paths, args.db_url))
    if args.json:
        _print_json(report)
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
