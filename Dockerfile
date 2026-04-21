# Multi-stage build: copy `uv` from its official image, resolve deps in a
# builder stage, then ship a slim runtime with only the virtualenv + app.
# `uv sync --frozen --no-dev` pins the production closure from uv.lock so
# the image is reproducible and dev-only tools (ruff, mypy, pytest) stay
# out of production.

FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install deps first (cached layer) before copying source.
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


FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app /app

# Render injects $PORT; default to 8080 locally.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn fleetwise.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
