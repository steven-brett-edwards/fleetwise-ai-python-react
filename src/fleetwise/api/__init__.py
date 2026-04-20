"""HTTP surface (FastAPI routers).

One module per resource: `vehicles`, `maintenance`, `work_orders`. Each
exposes an `APIRouter` that `fleetwise.main` mounts under `/api`.
"""
