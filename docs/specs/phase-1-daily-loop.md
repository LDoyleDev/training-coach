# Phase 1: the daily loop

Goal: Liam trains from the morning Telegram message and logs by voice or text, with targets,
personal bests and progression flags. Milestone: **Phase 1 - Daily loop**. Target version: 0.2.0.

Each step below is one GitHub issue and one PR, in this order. Steps list acceptance criteria;
an issue is done when all are met and `make check` passes.

## Data model (step 1-A)

| Table | Purpose | Key columns |
| --- | --- | --- |
| `exercises` | Movement family | id, slug, name, kind (`reps`/`seconds`/`duration_min`), muscle_groups |
| `ladder_steps` | Variations, easiest first | id, exercise_id, position, name, cue |
| `session_templates` | Ordered sessions in the cycle | id, position, slug, name, focus, is_rest_optional |
| `template_items` | Exercises in a session | id, template_id, position, exercise_id, sets, rep_min, rep_max, per_side |
| `exercise_state` | Current ladder step per exercise | exercise_id (PK), ladder_step_id, updated_at |
| `plan_state` | Queue pointer (single row) | id=1, next_template_id, updated_at |
| `settings` | User settings (single row) | id=1, morning_time, nudge_time, nudges_enabled, paused |
| `workouts` | One training session; several per day allowed (ADR-0014) | id, local_date, template_id (NULL = extra session), status (`done`/`rest`/`skipped`), created_at |
| `set_logs` | One set; only for `done` workouts (service rule) | id, workout_id, exercise_id, ladder_step_id, set_no, value, side (`both`/`left`/`right`, never NULL) |
| `events` | Audit log | id, at, kind, payload (JSON, no secrets or transcripts) |

All timestamps UTC (`UTCDateTime` rejects naive datetimes). `local_date` is the date in Europe/Berlin.
Database constraints guard enums, ranges (set value 0-3600, set_no >= 1, rep_max >= rep_min),
unique ladder positions, unique sets per workout/exercise/set/side, single-row tables
(`plan_state`, `settings`), and composite foreign keys so a referenced ladder step always
belongs to the same exercise. Migrations never import application code.

## Steps

### 1-A Data model and migrations
- Models above in `db/models.py`, one Alembic migration with downgrade.
- `alembic check` clean in CI; migration test upgrades and downgrades.

### 1-B Seed the plan
- `training-coach seed` (`make seed`) loads `seed/plan.toml` idempotently (re-running changes
  nothing). The container runs it on every start, after migrations.
- The file is validated first (Pydantic, unknown keys rejected): slugs, kinds, ladder `start`,
  rep ranges, references between sessions and exercises.
- Upserts by slug/position: edits and additions apply; sessions can be reordered or inserted
  anywhere. Nothing is deleted: removing a session from the file is rejected (it would leave an
  orphan in the queue) and needs a data migration instead. A failed seed does not stop the
  container; it serves with the existing plan and logs `seed.failed`. Progress is never reset: existing exercise state, queue pointer and settings stay.
- New exercises start at their `start` ladder step; a new database points at the first session.
- To change the plan: edit `plan.toml` in a PR; it applies on the next deploy.

### 1-C Session queue and targets (pure domain)
- `domain/queue.py`: next session; advance on done/rest; no advance on nothing logged
  (ADR-0006). Tests: skip, double skip, rest, wrap-around, DST dates.
- `domain/targets.py`: target per set from the last session of that exercise at the same
  ladder step (+1 rep on the lowest sets, capped at rep_max); first time = rep_min.
- `domain/progression.py`: ready-to-progress rule from the product spec. Tests with fixtures.

### 1-D Morning message, nudge and settings
- JobQueue daily job at `settings.morning_time` (Europe/Berlin), rescheduled when changed.
- Message: session name, exercises with ladder step and targets; buttons Start / Rest today / Swap.
- Evening nudge at `nudge_time` only if nothing logged and nudges enabled.
- `/settings`: change morning time (buttons for common times + free entry `HH:MM`), nudge
  on/off, pause. `/today`, `/week`, `/help`.
- Tests: owner-only for every handler; schedule across DST; nudge suppressed when logged.

### 1-E Text logging with confirmation
- `domain/parser.py`: rule parser for "exercise n n n" lines; fuzzy match against today's
  exercises and aliases; numbers bounded (0-200 reps, 0-3600 s).
- Bot replies with a table of what it understood; buttons Save / Edit / Cancel; save writes
  `workouts` + `set_logs` in one transaction and advances the queue.
- Tests: parser table-driven (typos, units, "each side", extra words), confirm flow.

### 1-F Voice logging (Groq)
- `services/groq.py`: transcription (`whisper-large-v3-turbo`) and fallback JSON parse with a
  Pydantic schema; timeouts, retries, free-tier error handling (ADR-0008).
- Voice file downloaded to `/tmp`, deleted after transcription; transcript never logged.
- Rule parser first; LLM fallback only if rules fail; same confirm step (ADR-0007).
- If Groq fails: "Couldn't transcribe, please type it".
- Tests: mocked HTTP (respx or httpx MockTransport); hostile transcript cases.

### 1-G Feedback and progress
- After save: personal bests (best set, total reps per exercise/step), ready-to-progress
  prompt with buttons "Move up" / "Not yet".
- `/progress`: best recent sets per exercise and current ladder step.

### 1-H Backups and ops
- Nightly job: SQLite online backup to `data/backups/`, rotation (7 daily, 4 weekly).
- `scripts/pull-backup.sh` for the desktop (rsync over Tailscale).
- Runbook updated; restore rehearsed once and noted in the PR.

## Definition of done (phase)
- All steps merged; release PR merged as v0.2.0; deployed on the Pi.
- One real week of training logged through the bot.
