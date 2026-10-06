# Training Coach

A self-hosted training coach. A Telegram bot sends today's session each morning, takes your
workout log by voice or text, and tracks progress through bodyweight progression ladders. A
dashboard shows history and progress and can be shared read-only. Runs on a Raspberry Pi.

[![CI](https://github.com/LDoyleDev/training-coach/actions/workflows/ci.yml/badge.svg)](https://github.com/LDoyleDev/training-coach/actions/workflows/ci.yml)

## Status

Phase 0 (scaffold) done. Phase 1 (daily loop) in progress: see the
[milestone](https://github.com/LDoyleDev/training-coach/milestones) and
[phase 1 spec](docs/specs/phase-1-daily-loop.md).

## Quick start (development)

Requirements: [uv](https://docs.astral.sh/uv/), Node 22, make. On Windows, work inside WSL 2:
see [the Windows setup runbook](docs/runbooks/dev-environment-windows.md).

```bash
make setup                 # deps + git hooks
cp .env.example .env       # add a *development* bot token and your Telegram user ID
make dev-api               # API + bot on :8080
make dev-web               # dashboard on :5173
make check                 # everything CI runs
```

## Documentation

| | |
| --- | --- |
| [Product spec](docs/specs/product-spec.md) | What the app does, by phase |
| [Architecture](docs/architecture.md) | Components and request paths |
| [Decisions (ADRs)](docs/adr/README.md) | Why things are the way they are |
| [Threat model](docs/security/threat-model.md) | Security controls |
| [Runbooks](docs/runbooks/) | Windows dev setup, deploy, backup/restore, rotate secrets, GitHub setup |
| [Contributing](CONTRIBUTING.md) | Workflow, commits, releases |
| [CLAUDE.md](CLAUDE.md) | Instructions for Claude Code |

## Stack

Python 3.12 · FastAPI · python-telegram-bot · SQLAlchemy + Alembic · SQLite · React · Vite ·
Tailwind · Docker Compose · GitHub Actions · release-please
