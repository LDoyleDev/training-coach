# Architecture Decision Records

Accepted ADRs are binding. To change one, write a new ADR that supersedes it (`/adr` in Claude
Code). Template: [template.md](template.md).

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-python-fastapi-single-process.md) | Python + FastAPI, one process for API and bot | Accepted |
| [0003](0003-docker-compose-on-pi.md) | Deploy with Docker Compose on the Pi | Accepted |
| [0004](0004-react-vite-tailwind-dashboard.md) | Dashboard in React + Vite + Tailwind | Accepted |
| [0005](0005-git-workflow-and-releases.md) | Git workflow, commit convention and releases | Accepted |
| [0006](0006-session-queue-scheduling.md) | The plan is an ordered queue; missed sessions shift back | Accepted |
| [0007](0007-llm-output-is-untrusted-data.md) | LLM output is untrusted data, never an action | Accepted |
| [0008](0008-groq-transcription-and-parsing.md) | Groq for transcription and fallback parsing | Accepted |
| [0009](0009-telegram-long-polling-owner-only.md) | Telegram via long polling, owner-only | Accepted |
| [0010](0010-sqlite-on-sd-card.md) | SQLite on the SD card, with nightly backups | Accepted |
| [0011](0011-claude-github-action-subscription.md) | Claude GitHub Action on the owner's subscription | Accepted |
| [0012](0012-dashboard-auth-and-share-links.md) | Dashboard auth via Telegram, read-only share links | Accepted |
| [0013](0013-uv-for-python-dependencies.md) | uv and pyproject.toml for Python dependencies | Accepted |
| [0014](0014-multiple-workouts-per-day.md) | Several workouts per day | Accepted |
| [0015](0015-seed-failure-does-not-block-startup.md) | A failed plan seed does not block startup | Accepted |
| [0016](0016-queue-and-target-rules.md) | Queue edge cases and target rules | Accepted |
| [0017](0017-plan-follows-huberman-protocol.md) | The training plan follows Huberman's Foundational Fitness Protocol | Accepted |
