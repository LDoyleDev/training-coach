# syntax=docker/dockerfile:1.7
# Multi-stage build for the Raspberry Pi (linux/arm64). See ADR-0003.

# Base images are pinned by digest (the multi-arch index), so a tag moved upstream can't change
# what's built. Image names are written out in full, not built from an ARG, so Dependabot can
# read them and propose new digests monthly. CI pulls them through Google's Docker Hub mirror,
# set on the runner's Docker (ci.yml), which serves the same digests.

# --- 1. Dashboard ---------------------------------------------------------
FROM docker.io/library/node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Python dependencies ----------------------------------------------
FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS deps
COPY --from=ghcr.io/astral-sh/uv:0.8.17@sha256:e4644cb5bd56fdc2c5ea3ee0525d9d21eed1603bccd6a21f887a938be7e85be1 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

# --- 3. Runtime ------------------------------------------------------------
FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS runtime
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
# not (ADR-0015): the app serves with the plan already in the database and `seed` logs
# "seed.failed" with the reason, so a bad plan.toml can never crash-loop the container.
CMD ["sh", "-c", "alembic upgrade head && { training-coach seed || true; } && exec training-coach serve"]
