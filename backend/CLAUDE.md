# backend/CLAUDE.md

Rules for `backend/`. The root `CLAUDE.md` still applies.

## Layout

```
src/training_coach/
  config.py  logging.py  __main__.py   settings, structlog setup, CLI (serve | seed | openapi)
  api/        FastAPI app, routes, security middleware
  bot/        Telegram handlers (thin)
  domain/     pure logic: session queue, progression rules, parsing rules
  services/   use cases: logging a workout, sending the morning message, Groq client
  db/         models.py (all models), session.py, base.py, types.py
  seed/       plan.toml, the bundled training plan
migrations/   Alembic
tests/        mirrors src/: tests/api/, tests/bot/, tests/db/, tests/domain/, tests/services/
```

## Code rules

- Typing: mypy strict must pass. No `Any` in domain code. Every `# type: ignore[code]` names
  the error code (ruff `PGH` enforces it) and gives a reason in a comment.
- Per-person data (ADR-0029): use a session bound to the user (`make_session_factory(engine,
  user_id=...)`); it filters and stamps `user_id` itself. Never filter by user by hand, never
  use `session.connection()` or bulk insert/update for per-person data, and use an unbound
  session only for shared work (seed, linking the owner). New per-person tables inherit `Owned`.
- Database: every schema change is an Alembic migration with a working downgrade. Never edit
  an applied migration. SQLite is on an SD card: batch writes, no chatty per-second writes.
  Use `op.batch_alter_table` to alter columns; follow the naming convention in `db/base.py`.
- Time: store UTC (`datetime.now(UTC)`, columns use `db.types.UTCDateTime`); convert to
  `settings.tz` (Europe/Berlin) only at the edges. Scheduling must survive DST changes; test
  both transitions.
- Config: only through `training_coach.config.Settings` (`TC_` env vars; secrets as
  `SecretStr`). Add every new variable to `.env.example` with a comment.
- Logging: `structlog.get_logger(__name__)`, event names like `bot.log_saved`, key-value fields.
  Never log tokens, API keys, raw voice transcripts or body measurements. No `print` (ruff T20).
- External calls (Telegram, Groq): timeouts on every request, retries with backoff, and a
  user-facing fallback message when they fail.

## Tests

- Single test: `uv run pytest tests/api/test_app.py::test_healthz_reports_ok`.
- `tests/conftest.py`: `settings`, `client` (TestClient), `engine` and `session` (a SQLite file
  migrated to head, the real schema rather than `create_all`).
- `tests/factories.py`: row builders with defaults; override only what the test is about.
- `respx` fakes HTTP (Groq, Telegram); `time-machine` freezes or moves the clock. Tests never
  call a real external API and never sleep.
- `domain/` stays at 100% coverage; the whole backend at >= 80%.

## Gotchas

- Migrations run with SQLite foreign keys off (`migrations/env.py`): batch mode rebuilds a table
  by dropping it, and with keys on the drop cascades and deletes child rows. `env.py` runs
  `PRAGMA foreign_key_check` afterwards and fails the migration if anything dangles.
- A PTB `CommandHandler` only matches once the bot knows its username, so handler tests call
  `application.initialize()` with respx faking `getMe`. See `tests/bot/test_app.py`.
- `training-coach openapi` pins `info.version`, so a version bump never makes the dashboard
  types stale. Keep it that way.
