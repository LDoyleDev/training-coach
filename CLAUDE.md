# CLAUDE.md

Instructions for Claude Code working in this repo. Read this first, every session.

## What this is

Training Coach: a self-hosted training coach for one user (Liam), running on a Raspberry Pi 5.
A Telegram bot sends the day's session each morning, takes workout logs by voice or text, and
tracks progress. A dashboard (React) shows history and progress and can be shared read-only.
Later, an MCP endpoint lets Claude read and log data.

- Product spec: `docs/specs/product-spec.md`
- Current phase spec: `docs/specs/phase-1-daily-loop.md`
- Decisions: `docs/adr/` (accepted ADRs are binding)
- Security: `docs/security/threat-model.md`
- Architecture: `docs/architecture.md`

## Stack

- Backend: Python 3.12, FastAPI, python-telegram-bot (long polling), SQLAlchemy 2 + Alembic,
  SQLite, pydantic-settings, structlog. Dependencies via **uv** (`backend/`).
- Frontend: React 19 + TypeScript + Vite + Tailwind v4, tested with Vitest (`frontend/`).
- One process runs API + bot (ADR-0002). One Docker container on the Pi (ADR-0003).
- Transcription and fallback parsing: Groq free tier over HTTPS (ADR-0008).

## Commands (run from repo root)

```
make setup       # install deps + git hooks (once)
make check       # lint + typecheck + tests, backend and frontend. Must pass before any PR.
make format      # auto-fix formatting
make dev-api     # API + bot on :8080 with reload
make dev-web     # dashboard dev server, proxies to :8080
make migration m="describe change"   # autogenerate an Alembic migration
make migrate     # apply migrations
make seed        # load/update the training plan (idempotent, never resets progress)
```

Single test: `cd backend && uv run pytest tests/test_api.py::test_healthz_reports_ok`.

## Workflow (every task)

1. Work from a GitHub issue. One issue = one branch = one PR. Read the issue and the spec step it
   references before writing code.
2. Branch from up-to-date `main`: `feat/<issue-number>-short-slug` (or `fix/`, `docs/`, `chore/`).
   Never commit to `main` (a pre-commit hook blocks it; branch protection enforces it).
3. Write tests first or alongside. Keep coverage >= 80% (enforced).
4. Run `make check` until green. Do not open a PR with failing checks.
5. Commit with Conventional Commits: `feat(bot): send morning session`. Types: feat, fix, docs,
   style, refactor, perf, test, build, ci, chore, revert. Scopes: bot, api, web, db, domain,
   parser, scheduler, infra, docs.
6. Open the PR with `gh pr create`, title = conventional commit, body from the PR template, with
   `Closes #<issue>`. PRs are squash-merged; the title becomes the commit on `main`.
7. If you made a design decision that is not already in an ADR, add one (`/adr`) in the same PR.
8. Update docs in the same PR when behaviour changes (spec, runbook, README, CHANGELOG is automatic).

Never bump versions or edit `CHANGELOG.md` by hand: release-please does it from commit history.

## Code rules

- Layering: `domain/` is pure logic (no I/O, no framework imports, fully unit-tested);
  `services/` orchestrates domain + db + external APIs; `bot/` and `api/` are thin adapters.
- Typing: mypy strict must pass. No `Any` in domain code. No `# type: ignore` without a reason.
- Database: every schema change is an Alembic migration with a working downgrade. Never edit
  an applied migration. SQLite is on an SD card: batch writes, no chatty per-second writes.
- Time: store UTC (`datetime.now(UTC)`); convert to `settings.tz` (Europe/Berlin) only at the
  edges. Scheduling must survive DST changes; test both transitions.
- Config: only through `training_coach.config.Settings` (`TC_` env vars). Add every new variable
  to `.env.example` with a comment.
- Logging: `structlog.get_logger(__name__)`, event names like `bot.log_saved`, key-value fields.
  Never log tokens, API keys, raw voice transcripts or body measurements.
- External calls (Telegram, Groq): timeouts on every request, retries with backoff, and a
  user-facing fallback message when they fail.

## Security rules (non-negotiable; see threat model)

- The bot answers only `TC_TELEGRAM_ALLOWED_USER_ID`. Every handler uses the `owner_only`
  filter. Add a test for each new handler proving strangers are ignored.
- LLM output is untrusted data: parse into a Pydantic model, reject anything that does not
  validate, and show it to the user for confirmation before saving. LLMs never get tools and
  never trigger actions directly.
- Never read, print, or commit `.env` or any secret. Never paste secrets into issues, PRs,
  commits, logs or test fixtures. Use obviously fake values in tests (`123456:TEST-TOKEN`).
- Share links: random 32-byte tokens, stored hashed, with expiry; read-only; exclude
  measurements and photos.
- Dashboard auth: verify Telegram signatures (HMAC) with a freshness window; cookies are
  HttpOnly, Secure, SameSite=Strict.
- No raw SQL built from strings; use the ORM or bound parameters.
- New dependencies need a reason in the PR description; prefer the standard library.

## Where things go

```
backend/src/training_coach/
  config.py  logging.py  __main__.py
  api/        FastAPI app, routes, security middleware
  bot/        Telegram handlers (thin)
  domain/     pure logic: session queue, progression rules, parsing rules
  services/   use cases: logging a workout, sending the morning message, Groq client
  db/         models.py (all models), session.py, base.py
backend/migrations/   Alembic
backend/tests/        mirrors src layout
frontend/src/         dashboard
docs/adr/             decisions (NNNN-title.md)
docs/specs/           product + phase specs
docs/runbooks/        deploy, backup/restore, rotate secrets
scripts/              repo and ops scripts
```

## Deployment

Desktop -> PR -> merge -> on the Pi: `git pull && make up`. Never edit code on the Pi.
Details: `docs/runbooks/deploy.md`.
