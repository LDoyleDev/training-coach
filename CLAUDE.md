# CLAUDE.md

Instructions for Claude Code working in this repo. Read this first, every session.
Stack-specific rules live next to the code: `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

## What this is

Training Coach: a self-hosted training coach for one user (Liam), running on a Raspberry Pi 5.
The web app (React) is the main surface: today's session, the guided session, progress and
settings, signed in with passkeys (ADR-0035, ADR-0036). A Telegram bot sends reminders and takes
quick logs by voice or text. Later, an MCP endpoint lets Claude read and log data.

- Product spec: `docs/specs/product-spec.md`
- Current phase spec: `docs/specs/phase-1-daily-loop.md` (its Status table says what is done and next)
- Next phase (draft): `docs/specs/phase-2-overview.md`, decisions in `docs/specs/phase-2-decisions.md`;
  the multi-surface and health-data direction: `docs/specs/platform-and-health-data-proposal.md`
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
make check       # lint, types, tests, migration check, API types, build. Must pass before any PR.
make ci          # check + dependency audit (network)
make format      # auto-fix formatting
make dev-api     # API + bot on :8080 with reload
make dev-web     # dashboard dev server, proxies to :8080
make migration m="describe change"   # autogenerate an Alembic migration
make migrate     # apply migrations
make api-types   # regenerate dashboard API types after changing a response model (ADR-0020)
make seed        # load/update the training plan (idempotent, never resets progress)
```

## Workflow (every task)

1. Work from a GitHub issue. One issue = one branch = one PR. Read the issue and the spec step it
   references before writing code (`/start-issue <n>`).
2. Branch from up-to-date `main`: `feat/<issue-number>-short-slug` (or `fix/`, `docs/`, `chore/`).
   Never commit to `main` (a pre-commit hook blocks it; branch protection enforces it).
3. Write tests first or alongside. Coverage >= 80%, backend and frontend (enforced).
   **Every bug fix starts with a test that fails before the fix.**
4. Run `make check` until green. Do not open a PR with failing checks.
5. Commit with Conventional Commits: `feat(bot): send morning session`. Types: feat, fix, docs,
   style, refactor, perf, test, build, ci, chore, revert. Scopes: bot, api, web, db, domain,
   parser, scheduler, infra, docs. Say what changed and why; a subject can state a finding.
6. Ship with `/ship`: it runs `make check`, the `security-reviewer` subagent, and the
   `migration-reviewer` subagent when the diff touches the database, then opens the PR
   (title = conventional commit, template filled in, `Closes #<issue>`). PRs are
   squash-merged; the title becomes the commit on `main`. Never merge your own PR.
7. Keep PRs reviewable: aim for under ~400 changed lines, not counting lockfiles, generated
   files and migrations. If an issue needs more, split it into issues before starting.
8. If you made a design decision that is not already in an ADR, add one (`/adr`) in the same PR.
9. Update docs in the same PR when behaviour changes (spec, runbook, README).
   A PR that finishes a phase step also marks it done in that phase spec's Status table.

Never bump versions or edit `CHANGELOG.md` by hand: release-please does it from commit history.
A hook blocks edits to `CHANGELOG.md`, real `.env` files and migrations already on `main`, and
formats every file you edit (ADR-0021).

## Architecture rules

- Layering: `domain/` is pure logic (no I/O, no framework imports; a test enforces it);
  `services/` orchestrates domain + db + external APIs; `bot/` and `api/` are thin adapters
  that never query models themselves. The import-linter contracts in `backend/pyproject.toml`
  are the dependency map (`make lint` and CI run them); `tests/test_architecture.py` covers
  what they can't see (models re-exported by a service, `select` in a handler).
- One way in for each risky thing: settings via `config.Settings`, HTTP to Groq/Telegram via
  `services/`, database via `db/session.py`. Don't add a second path.
- Details (typing, database, time, logging, external calls): `backend/CLAUDE.md`.

## Security rules (non-negotiable; see threat model)

- The bot answers only `TC_TELEGRAM_ALLOWED_USER_ID`. Every handler uses the `owner_only`
  filter. Add a test for each new handler proving strangers are ignored.
- LLM output is untrusted data: parse into a Pydantic model, reject anything that does not
  validate, and show it to the user for confirmation before saving. LLMs never get tools and
  never trigger actions directly.
- Never read, print, or commit `.env` or any secret. Never paste secrets into issues, PRs,
  commits, logs or test fixtures. Use obviously fake values in tests (`123456:TEST-TOKEN`).
- Sharing is a picture the bot sends on `/share` (ADR-0050), with no public link; it never
  shows measurements, readiness answers or photos.
- Web sign-in (ADR-0036): passkeys, a one-time bot link (hashed, single use, 10 minutes) to
  start or recover; session cookies HttpOnly, Secure, SameSite=Strict; every route declared
  public or owner-only, enforced by a test.
- No raw SQL built from strings; use the ORM or bound parameters.
- New dependencies need a reason in the PR description; prefer the standard library.

## Where things go

```
backend/     API, bot, domain, services, db, migrations, tests   (see backend/CLAUDE.md)
frontend/    dashboard                                            (see frontend/CLAUDE.md)
docs/adr/    decisions (NNNN-title.md)       docs/specs/     product + phase specs
docs/security/  threat model                 docs/runbooks/  deploy, backup/restore, secrets
docs/legal/  privacy notice, Impressum (drafts, unpublished)
scripts/     repo and ops scripts            .claude/        commands, subagents, hooks
```

## Deployment

Desktop -> PR -> merge -> release PR merged -> the Pi deploys the new tag itself within about
15 minutes (ADR-0030). Never edit code on the Pi. Details: `docs/runbooks/deploy.md`.

## Gotchas

Things that cost time once. Add one when a mistake is worth not repeating; delete it when the
cause is gone.

- Changed a Pydantic response model? Run `make api-types` and commit the result, or
  `make check` fails with "API types are stale".
- Tests import builders as `from tests import factories`; the migrated-DB fixtures `engine`
  and `session` live in `tests/conftest.py`. Don't recreate them per file.
- Develop in WSL 2, not natively on Windows (ADR-0018, `docs/runbooks/dev-environment-windows.md`).
  Natively, AVG's HTTPS scanning breaks TLS: use `git config http.sslBackend schannel` and
  `uv ... --system-certs`; there is no `make`.

## Keeping this file useful

This file is loaded into every session, so it holds only stable rules and pointers: under 150
lines, no status, no progress notes, no changelog, no ADR index. Status lives in GitHub issues
and milestones; history lives in git; decisions live in `docs/adr/`. If a rule here stops
matching the code, fix whichever one is wrong in the same PR.
