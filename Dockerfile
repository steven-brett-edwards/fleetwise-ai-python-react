# Multi-stage build.
#
# Stage 1 (`frontend`): build the React SPA with Node. Output is a static
# bundle in `/frontend/dist` copied into the final image so FastAPI can
# serve it via StaticFiles on the same origin as the API (no prod CORS,
# one Render service, no split deploy to wire up).
#
# Stage 2 (`builder`): resolve Python deps with `uv sync --frozen` so the
# image is reproducible from uv.lock, then copy the app source.
#
# Stage 3 (`runtime`): slim Python image with just the venv + app + built
# frontend. Dev tools (ruff, mypy, pytest, Node) stay out of production.

FROM node:20-alpine AS frontend

WORKDIR /frontend

# Install deps first (cached layer) before copying source.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Static content: SOP markdown corpus for RAG ingestion. Lives outside
# /app/data so the Render disk mount at /app/data doesn't shadow it.
COPY data/documents ./documents

# Inspection-CSV fixture corpus for the Phase 10 ETL pipeline. Loaded
# at boot by `ingest_inspections_if_empty` so the deployed demo can
# answer "what did the latest inspection on V-2020-0010 find?". Same
# /app/foo (not /app/data/foo) layout as documents above; the matching
# INSPECTIONS_DIR env var in render.yaml points the code at it.
COPY data/inspections ./inspections


FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app /app
COPY --from=frontend /frontend/dist /app/frontend/dist

# Render injects $PORT; default to 8080 locally.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn fleetwise.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
