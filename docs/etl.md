# ETL pipeline — vehicle inspection ingestion

Phase 10 of the migration plan. Ingests messy external vehicle-inspection
CSVs, normalizes them with an LLM-mapped header layer, and loads them
into a `vehicle_inspections` table that the chat agent can read via the
`get_recent_inspections` tool.

## Quick run

```bash
# Walk through the 12 committed fixture CSVs.
uv run fleetwise-etl ingest data/inspections/*.csv
```

Sample output:

```
ETL ingest report
================================================================
data/inspections/inspections-2026-03-batch-a.csv
  rows total       : 8
  rows loaded      : 8
  rows skipped     : 0  (already in DB)
  rows orphaned    : 0
  rows rejected    : 0
... (one block per file) ...
================================================================
Totals: loaded=82, skipped=0, orphaned=3, rejected=0
```

Re-run the same command and `loaded` drops to `0` — the pipeline is
idempotent on a `(source_file, source_row_hash)` unique index.

Once data is loaded, ask the chat agent:

> What did the latest inspection on V-2020-0015 find?

The agent dispatches `get_recent_inspections` and returns the matching
records (newest first), surfacing orphan rows with an explicit
`Orphan: true` flag so the LLM can call out the data-quality note.

## Architecture

```
data/inspections/*.csv
        │
        ▼
   extract.read_csv  ──── headers + raw row tuples
        │
        ▼
   mapper.map_headers ── canonical-name lookup; LLM call for unknowns;
        │                disk-backed cache so repeat shapes are free
        ▼
   transform.transform_row ── coerce date / mileage / pass-fail; compute
        │                     deterministic source_row_hash
        ▼
   load.load_row ──── upsert via the inspection repository's
        │             (source_file, source_row_hash) unique index
        ▼
   vehicle_inspections table
        │
        ▼
   ai.tools.inspection.get_recent_inspections (chat tool)
```

Each stage is independently testable. The pipeline orchestrator is the
only stage that owns a session; inner stages are pure or take a session
as a parameter.

## Design notes

### LLM-mapped headers, with a disk cache

Real-world inspection CSVs use heterogeneous header names: `Asset Number`,
`Vehicle ID`, `unit_no`, `vehicle_asset` all refer to the same field.
The mapper is a two-phase resolver:

1. **Cheap path.** Case-insensitive exact match against the canonical
   names (`asset_number`, `inspected_at`, …). Resolves the easy cases
   without touching an LLM.
2. **LLM path.** For headers the cheap path didn't resolve, ask the
   provider's structured-output endpoint for a mapping. The result is
   keyed on a sorted-lowercase fingerprint of the input header set and
   persisted to `data/etl-cache/header-mappings.json` so subsequent
   runs over the same shape skip the network entirely.

A real-world consequence: ingesting 12 files with 6 distinct header
shapes makes 6 LLM calls the first time and 0 on every subsequent run.
Cost-conscious by construction.

### Orphan handling: load, don't drop

When a CSV row references an asset number that isn't in the seeded fleet,
the pipeline loads the row anyway with `vehicle_id=None` and the
original asset number preserved on `unmatched_asset_number`. The
rationale is one we'd defend in a code review: a data-pipeline's job
is to *normalize and load*, not to silently drop data that arrived in
our inbox. The chat tool surfaces orphans with an explicit flag so the
LLM can call out the data-quality issue rather than answer "no
inspections" for an asset that has them.

### Idempotency contract

`(source_file, source_row_hash)` is a unique constraint on
`vehicle_inspections`. The hash is sha256 of the canonical post-transform
payload, sorted-keyed so the same logical row produces the same hash on
every run. Re-ingesting a file is a no-op upsert; the pipeline returns a
`rows_skipped_existing` count for transparency.

If the source file ever changes (e.g. a row is corrected upstream),
the hash changes and the corrected row gets a new DB id — the original
remains, preserving history. That's a deliberate choice; alternative
designs that overwrite are also reasonable, but the audit-trail behavior
matches what a municipal-fleet operator would actually want.

### Why not run on backend startup?

The seed pipeline (`seed_if_empty`) runs in the FastAPI lifespan because
the data is canonical: every dev / prod environment wants the same 35
vehicles. The ETL pipeline is the opposite — it's *demonstrating* a
human-in-the-loop ingestion against external CSVs. Auto-running it on
boot would muddy the framing ("this is a real pipeline that you run as
a job") and make idempotency-test failures show up as boot crashes
instead of CLI errors.

## Common operator gotchas

- **No API key exported, lots of rejections.** Files with non-canonical
  headers need the LLM mapper. Without `OPENAI_API_KEY` (or
  `ANTHROPIC_API_KEY`, depending on `AI_PROVIDER`), the mapper's
  cheap path resolves the literal-canonical files and rejects the rest
  with "missing required mapped headers". Export a key and rerun.
- **Fresh DB, every row is an orphan.** The CLI calls
  `Base.metadata.create_all` on the target DB but does NOT run
  `seed_if_empty`. Point `--db-url` at the dev / prod DB that already
  has the 35-vehicle seed, or run `uv run uvicorn fleetwise.main:app`
  once first to populate the default `fleetwise.db`.

## Reference

- Source: [`src/fleetwise/etl/`](../src/fleetwise/etl/)
- Repository (DB writes): [`src/fleetwise/data/repositories/inspection.py`](../src/fleetwise/data/repositories/inspection.py)
- Chat tool: [`src/fleetwise/ai/tools/inspection.py`](../src/fleetwise/ai/tools/inspection.py)
- Tests: `tests/unit/test_etl_*.py`, `tests/integration/test_etl_*.py`,
  `tests/unit/test_tools/test_inspection_tool.py`
- Fixture CSVs: [`data/inspections/`](../data/inspections/) (12 files,
  82 records, 3 intentional orphans referencing `V-9999-0001`)
