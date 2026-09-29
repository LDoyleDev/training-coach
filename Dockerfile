# syntax=docker/dockerfile:1.7
# Multi-stage build for the Raspberry Pi (linux/arm64). See ADR-0003.

# --- 1. Dashboard ---------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Python dependencies ----------------------------------------------
FROM python:3.12-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

# --- 3. Runtime ------------------------------------------------------------
FROM python:3.12-slim AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=deps --chown=app:app /app /app
COPY --from=web --chown=app:app /web/dist /app/web
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TC_ENVIRONMENT=production \
    TC_DATABASE_URL=sqlite:////data/training_coach.db \
    TC_WEB_DIST_DIR=/app/web
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4).status == 200 else 1)"
# Migrations and the plan seed run on every start; both are idempotent and never reset progress.
# A failed migration stops startup (the schema would not match the code). A failed seed does
# not: the app serves with the plan already in the database, so a bad plan.toml can never
# crash-loop the container. Check `make logs` for "seed.failed" after deploying plan changes.
CMD ["sh", "-c", "alembic upgrade head && { training-coach seed || echo '{\"event\": \"seed.failed\", \"level\": \"error\"}'; } && exec training-coach serve"]
