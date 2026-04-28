"""ETL pipeline for messy external vehicle-inspection CSVs.

The pipeline normalizes header names (LLM-mapped, with on-disk cache),
coerces messy date / mileage / pass-fail values, computes a deterministic
row hash for idempotency, resolves ``asset_number`` -> ``vehicle_id``
when possible, and upserts into ``vehicle_inspections``. Orphan rows
(asset numbers not in the seeded fleet) are loaded with
``vehicle_id=None`` and the original string preserved on
``unmatched_asset_number`` -- the pipeline normalizes and loads, it
doesn't silently drop data that arrived in our inbox.

Entry points:

- ``fleetwise.etl.pipeline.run_pipeline`` -- programmatic.
- ``fleetwise.etl.cli:main`` -- ``fleetwise-etl ingest <glob>...``.
"""
