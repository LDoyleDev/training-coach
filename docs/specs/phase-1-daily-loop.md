# Phase 1: the daily loop

Goal: Liam trains from the morning Telegram message and logs by voice or text, with targets,
personal bests and progression flags. Milestone: **Phase 1 - Daily loop**. Target version: 0.2.0.

Each step below is one GitHub issue and one PR, in this order. Steps list acceptance criteria;
an issue is done when all are met and `make check` passes.

## Status

Keep this table current: the PR that finishes a step marks it done here.

| Step | Issue | Status |
| --- | --- | --- |
| 1-A Data model and migrations | #7 | Done (#15) |
| 1-B Seed the plan | #8 | Done (#17, plan aligned with Huberman in #27) |
| 1-C Session queue and targets | #9 | Done (#19) |
| 1-D Morning message, nudge and settings | #10 | Done (#43, #46 with ADR-0022, and the settings and nudge PR) |
| 1-E Text logging with confirmation | #11 | Done (#54 parser, #55 save, and the bot flow PR) |
| 1-F Voice logging (Groq) | #12 | **Next** |
| 1-G Feedback and progress | #13 | Not started |
| 1-H Backups and ops | #14 | Not started |

Also in this milestone: #18 (guard ladder-step edits that would remap logged history; done).
Built outside the step list: the public plan page and
`GET /api/plan` (#32, ADR-0019). The bot sends the morning session with Start / Rest today / Swap buttons and an evening nudge, answers `/today`, `/week`, `/settings` and `/help`, and takes typed workout logs with a confirm step.

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
  anywhere. Removing a session or shortening a ladder is rejected before any write (history
  depends on them) and needs a data migration. Ladder steps are matched by position, so a step
  that logged sets or current progress use can't change name unless the exercise lists it in
  `renames = { "old" = "new" }`; new steps go at the end of a ladder (#18).
- Items removed from a session are deleted. A failed seed logs `seed.failed` with the reason and does not stop the container (ADR-0015). Progress is never reset: existing exercise state, queue pointer and settings stay.
- New exercises start at their `start` ladder step; a new database points at the first session.
- To change the plan: edit `plan.toml` in a PR; it applies on the next deploy.

### 1-C Session queue and targets (pure domain)
- `domain/queue.py`: next session; advance on done/rest of the session at the pointer; no
  advance on nothing logged, skipped, extra or out-of-order sessions (ADR-0006, ADR-0016).
  Tests: skip, double skip, rest, wrap-around, two sessions a day, DST dates.
- `domain/targets.py`: target per set from the last session at the same ladder step: all equal
  -> +1 each, otherwise +1 on sets below the best; capped at rep_max; no jump up to rep_min;
  first time = rep_min (ADR-0016). Example: 8/7/6/5 -> 8/8/7/6.
- `domain/progression.py`: ready when all planned sets hit rep_max in the last two sessions at
  the step; weaker side counts for unilateral work; `top_of_ladder` at the last step.
- CI enforces 100% coverage of `domain/` and a test forbids framework/I/O imports there.

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
