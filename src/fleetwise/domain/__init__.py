"""Domain layer: enums, entities, hybrid properties.

Pure types with no infrastructure dependencies (no FastAPI, no HTTP, no
config). Repositories live one layer out in `fleetwise.data` and depend on
this package; the API layer depends on both.
"""
