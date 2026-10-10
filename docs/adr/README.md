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
| [0012](0012-dashboard-auth-and-share-links.md) | Dashboard auth via Telegram, read-only share links | Accepted; sign-in superseded by 0036 |
| [0013](0013-uv-for-python-dependencies.md) | uv and pyproject.toml for Python dependencies | Accepted |
| [0014](0014-multiple-workouts-per-day.md) | Several workouts per day | Accepted |
| [0015](0015-seed-failure-does-not-block-startup.md) | A failed plan seed does not block startup | Accepted |
| [0016](0016-queue-and-target-rules.md) | Queue edge cases and target rules | Accepted (targets superseded by 0027) |
| [0017](0017-plan-follows-huberman-protocol.md) | The training plan follows Huberman's Foundational Fitness Protocol | Accepted |
| [0018](0018-develop-in-wsl2-on-windows.md) | Develop in WSL 2 on the Windows desktop | Accepted |
| [0019](0019-public-plan-endpoint.md) | The bundled training plan is public at GET /api/plan | Accepted |
| [0020](0020-generated-api-types.md) | Dashboard API types are generated from the OpenAPI schema | Accepted |
| [0021](0021-claude-code-guardrails.md) | Claude Code guardrails: hooks, review subagents, a lean CLAUDE.md | Accepted |
| [0022](0022-swap-and-rest-buttons.md) | What Swap and Rest today do to the queue | Accepted |
| [0023](0023-model-fallback-only-suggests.md) | The model fallback only suggests; the rule parser decides | Accepted |
| [0024](0024-backups-run-in-the-app-not-the-bot.md) | Backups run in the app, not the bot, and only a complete copy counts | Accepted |
| [0025](0025-personal-bests-and-progress-prompts.md) | Personal bests and the "ready to progress" prompt | Accepted |
| [0026](0026-multi-user-direction.md) | Built for one, designed for many | Accepted |
| [0027](0027-progressive-overload-step.md) | Progressive overload step of about 10% of the range | Accepted |
| [0028](0028-training-blocks.md) | Optional 4-week strength and hypertrophy blocks | Accepted |
| [0029](0029-sessions-bound-to-a-user.md) | Per-person data is scoped by binding the session to a user | Accepted |
| [0030](0030-deploy-releases-from-a-timer.md) | The Pi deploys new releases itself, from a timer | Accepted |
| [0031](0031-exercise-pairs-and-work-order.md) | Resistance sessions are done in fixed pairs, listed set by set | Accepted |
| [0032](0032-stretching-after-resistance.md) | Stretching after a resistance session is chosen for the muscles worked | Accepted |
| [0033](0033-logging-a-past-day.md) | A past day is logged with a date line, and catching up moves the queue | Accepted |
| [0034](0034-plan-changes-keep-history-per-exercise.md) | Plan changes keep history per exercise | Accepted |
| [0035](0035-web-app-first-telegram-for-reminders.md) | The web app is the main surface; Telegram is for reminders | Accepted |
| [0036](0036-sign-in-with-passkeys-and-a-telegram-link.md) | Sign in with passkeys, started and recovered with a Telegram link | Accepted |
| [0037](0037-baseline-tests-as-test-days.md) | Baseline tests are test days, defined in plan.toml, entered in the web app | Accepted |
| [0038](0038-test-days-wait-in-front-of-the-queue.md) | Test days stand in front of the queue while a round is due | Accepted |
| [0039](0039-progress-photos-in-the-database.md) | Progress photos are kept in the database, cleaned of their metadata | Accepted |
| [0040](0040-passkey-first-sign-in-with-telegram-recovery.md) | Passkey first, Telegram for recovery, and an alert for every sign-in change | Accepted |
