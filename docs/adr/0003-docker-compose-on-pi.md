# ADR-0003: Deploy with Docker Compose on the Pi

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The Pi also runs Vybe (FastAPI, Redis, Docker). The coach must not interfere with it, must be
easy to update and roll back, and must be hard to break out of if compromised.

## Decision

A multi-stage Dockerfile (Node builds the dashboard, uv installs Python deps, slim runtime) and
`compose.yaml` with one `app` service. Hardening: non-root user (uid 10001), read-only root
filesystem, `cap_drop: ALL`, `no-new-privileges`, memory limit, own Docker network, port
published on `127.0.0.1` only. cloudflared on the host is the only way in from the internet.
Images are built on the Pi (arm64). CI builds the image on amd64 to catch Dockerfile errors.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Docker Compose (chosen) | Isolation from Vybe, reproducible, easy rollback (`git checkout vX && make up`) | Image builds on the Pi take a few minutes |
| systemd + venv | Lighter | Shares host Python, weaker isolation, messier rollback |
| Prebuilt images in GHCR | Fast deploys | Registry auth + multi-arch builds; not worth it for one device yet |

## Consequences

- `data/` on the host must be owned by uid 10001 (see deploy runbook).
- Migrations run on container start (`alembic upgrade head`).
