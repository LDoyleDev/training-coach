# Plans per person (builder step 5): what reads the plan, and a draft migration

Status: **inventory as of v1.9.0 (30 Oct 2026), reviewed against 1.17.0 on 6 Nov 2026 (below);
released in 1.18.0 on 7 Nov 2026 (#578-#581); the order is under "The build".**
The open points are answered: the import ships
with step 5 (1 Nov 2026), the migration refuses if anyone but the owner exists (5 Nov 2026), one
database with each person's rows, starters in `plan.toml` and notes in `name` (6 Nov 2026).
Nothing here changes the schema. Builder step 5 (`program-builder.md`, option A2, ADR-0073)
makes `session_templates`, `template_items` and `plan_versions` per person. This file lists every
place that reads or writes those tables and `plan_state`, so the step can be checked against it.
The tests that pin it: `backend/tests/api/test_two_people_plans.py`.

## Ids that point into the plan tables

| From | To | On delete | Notes |
| --- | --- | --- | --- |
| `template_items.template_id` | `session_templates.id` | CASCADE | Unique `(template_id, place, position)` |
| `template_items.exercise_id` | `exercises.id` | RESTRICT | Into the catalogue, which stays shared |
| `plan_state.next_template_id` | `session_templates.id` | RESTRICT | One row per person |
| `plan_state.queued` | session ids, JSON | none | Swapped sessions (ADR-0022); `today.position` drops unknown ids |
| `workouts.template_id` | `session_templates.id` | RESTRICT | Empty for an extra |
| `workouts.plan_version_id` | `plan_versions.id` | RESTRICT | Set in the INSERT by `models._plan_version` |
| `session_progress.template_id` | `session_templates.id` | CASCADE | A guided session in progress |
| `events.payload` | session ids, JSON | none | `queue.rest`, `queue.pushed`, `queue.swapped`, `queue.picked`, and the `undo` snapshots (`[pointer, queued]`) that `workout.logged` and the queue events carry |
| `log_proposals.payload` | `template_id`, JSON | none | A proposal's target session |
| `replaced_workouts.data` | `template_id`, `plan_version_id`, JSON | none | Put back by `day_clash` on undo |
| Telegram buttons | `q:<action>:<template id>` | none | The morning message's Start, Rest, Swap (`bot/buttons.py`) |

Shared keys today: `session_templates.position` and `.slug` are unique, and so is
`plan_versions.since`. All three become unique per person.

## What the seed does with each today

`services/seed.apply_seed`, run unbound on every start (Dockerfile), on `make seed` and by erase:

- **`session_templates`**: upserts every session by slug, with its home, gym and away versions; reorders positions (parked out of the
  way first); refuses to remove a session (`_preflight`).
- **`template_items`**: makes each version (home, gym) match `plan.toml` by position: updates,
  appends, deletes items past the plan's last (`_version`).
- **`plan_versions`**: upserts by date, renames, deletes ones no workout records, refuses to drop
  a recorded one (`_versions_preflight`). Then a bulk UPDATE brings every person's workouts to
  the version in force on their date (`_apply_versions`, `all_users`).
- **`plan_state`**: adds a row at the first session for each person who has none; never moves one.
- Everything else here (`session_progress`, the JSON ids) it leaves alone.

## Reads and writes, by place

"Bound" means the session is bound to one person (ADR-0029), so the run-time filter will scope the
read once the table is `Owned`. After step 5 every row below is that person's: the signed-in
person on the web, the connection's person over MCP, the owner in the bot and its jobs.

### Already scoped by the binding (no code change, beyond the table becoming `Owned`)

| Where | What it does |
| --- | --- |
| `services/users.py:plan_state` | The person's queue row; every queue reader goes through it |
| `services/today.py:_order`, `position`, `session_plan` | The cycle in order; the queue position (dropping unknown queued ids); one session with its home and gym items by id |
| `services/guided.py:today`, `_run_done`, `save`, `_save_after_run`, `pending` | Today's guided plan; the day's done conditioning workout (join on the session's kind); the session of a kept `session_progress` row |
| `services/queue_actions.py:_state_at`, `_order`, `rest_today`, `push_to_tomorrow`, `swap_next`, `pick`, `next_up`, `choices` | Rest, Push, Swap, Pick: read sessions by id and in order, write `plan_state`, add `queue.*` events with ids |
| `services/workout_log.py:target`, `next_session_name`, `_named`, `_session_line`, `_inferred`, `_commit`, `_place`, `_order`, `save`, `_save_past`, `strength_on` | Typed and voice logs: today's or the named session, matching names and exercises, moving the queue on save |
| `services/workout_log.py:catalogue` | Every item's exercise, side and session: **no join to `session_templates`** |
| `services/cardio_totals.py:targets` | The week's planned cardio minutes: items joined to exercises only, **no join to `session_templates`** |
| `services/progress.py:_items`, `_item`, `overview` | Each exercise's prescription and the standings in plan order |
| `services/day_log.py:choices`, `plan`, `save_sets` | The Log page: every session, a session's targets, saving a past day |
| `services/day_view.py:logged`, `services/home.py:_recent`, `services/day_clash.py:recorded` | Session names for logged days |
| `services/review.py:planned_sessions` | Sessions in the cycle (a count with `select_from`: check the filter reaches it) |
| `services/session_times.py:by_session` | Timed sessions in plan order |
| `services/stretching.py:worked`, `_strength_workout` | A workout's session's muscles, for the stretches after it |
| `services/undo.py:snapshot`, `_name`, `apply` | The queue before and after a change, and putting it back |
| `services/ai_summary.py:_position`, `_sessions` | The MCP summary's plan position and session names |
| `services/export.py:archive` | `plan_state` in the tables; session and version names under `reference` |

`catalogue` and `targets` are why `template_items` needs its own `user_id`: scoped only through
its session, they would add up everyone's items.

**Ids from the client.** `/api/log/plan`, `POST /api/log`, `POST /api/today/{rest,push,next,pick}`,
the guided session's progress and a proposal's save all take a session id from the browser or the
AI. Bound reads make another person's id "not found" after step 5; the canary should then name
one in its `OTHERS` table.

### Reads the binding can't scope (change in step 5)

| Where | Today | After step 5 |
| --- | --- | --- |
| `db/models.py:_plan_version` (the `before_insert` hook) and `version_on` | The version in force, as a subquery in the workout's INSERT | Flush statements skip `do_orm_execute`, so the subquery is not filtered: `version_on` must take the workout's `user_id` |
| `services/day_clash.py:_date` | `version_on(day)` in a flushed UPDATE | The same: pass the person |
| `services/seed.py:_apply_versions` | Bulk UPDATE of everyone's workouts (`all_users`) | Correlate on each workout's own person, or move into the copy |
| `api/plan.py:build_plan_view` (`GET /api/plan`) | **Reads `plan.toml`**, not the database | The person's sessions from a bound session |
| `services/coverage.py:plan_coverage` (`GET /api/plan/coverage`) | **Reads `plan.toml`** sessions, with the person's steps | The person's sessions |
| `services/seed.py:_preflight` | Reads `SessionTemplate.slug` unbound | Raises once the table is `Owned`; the guard goes with the seed's new job |
| `services/erase.py:erase` | Deletes the person, then runs the whole seed (everyone's plan) | Deletes the person's workouts and queue row first (see "Erase"), then copies a starter for that person only |

### Readers of `plan.toml` that stay shared (the catalogue)

`today._summaries`, `today._worked`, `guided._kinds`, `guided._left`, `review._volume`,
`stretching.worked` (muscle weights), `blocks._load_kits`, `equipment.step_needs`,
`equipment.unlocks`, `fitness_tests.tests`, `mobility_flow.flow_for`. They read exercises,
stretches, tests and mobility, not sessions.

### What reads across people

- **The bot and its jobs** (morning, nudge, weekly review, band, proposals): one session factory
  bound to the owner (`api/app.py`). Members get no bot until multi-user's Telegram step, so
  nothing changes. The buttons carry template ids, which stay valid for the owner (below).
- **The seed**: unbound by design; the ladder, version and test guards read everyone with
  `all_users`.
- **The export**: bound. After step 5 the three plan tables are the person's own data, so they
  move from `reference` into `TABLES`. No test holds `TABLES` to the `Owned` models (erase has
  one for the cascade); step 5 could add it.
- **MCP tools**: bound to the connection's person (`api/mcp.py`); `get_summary` reads the queue
  and session names.
- **Erase**: unbound (it deletes the user row), then the seed.
- **Scripts and runbooks**: none query these tables.

### Writes

The seed (a starter for someone with no plan), `plan_edit.save` (the editor; with ADR-0093 also
adding, retiring and deleting sessions), `plan_import.save` (the owner's import), `gym_version.write`
and `walkthrough._swap` (which deletes the old sessions) write `session_templates`,
`template_items` and `plan_versions`, each for the bound person. `plan_state` is
written by the seed (new rows), `queue_actions`, `workout_log._commit`, `undo.apply` and the
guided save, all bound. `workouts.plan_version_id` is written by the hook, `day_clash._date` and
the seed.

## Tests

- **Pass now, keep passing:** one person's progress through the plan (a logged day, a pushed
  session, a level) changes nothing the other sees on any signed-in GET route or in the MCP
  summary.
- **`xfail(strict=True)` until step 5:** an edit to my sessions leaves yours alone; the Plan page
  and body map show my own sessions; a session and its items are one person's; a plan version I
  save never lands on your workouts (the `version_on` gap above); the seed changes nobody's
  sessions. Step 5 removes each marker and the test must pass.
- **Step 5 adds:** the three tables to `test_user_scope`'s list, a template id in the canary's
  `OTHERS`, the migration's own test, and the import's (it ships with step 5, below).

## Draft: the 5b migration (for review, not written)

**The owner keeps the rows and ids they have.** Stamping `user_id = 1` on today's shared rows
means no id in workouts, the queue, guided progress, events, proposals, replaced workouts or a
Telegram button moves. Only copies for other people need new ids.

1. **Columns** (batch mode; foreign keys are off in migrations and `env.py` checks them after):
   - `session_templates`: `user_id` (not null, `users.id`, CASCADE, indexed); unique
     `(user_id, position)` and `(user_id, slug)` in place of the single-column ones; unique
     `(user_id, id)` as a target for the composite keys below.
   - `template_items`: `user_id`; `(user_id, template_id)` to `session_templates (user_id, id)`,
     CASCADE, in place of the single-column key, so an item can't sit in another person's session.
   - `plan_versions`: `user_id`; unique `(user_id, since)`; unique `(user_id, id)`.
   - `workouts`: `(user_id, template_id)` and `(user_id, plan_version_id)` composite keys, RESTRICT.
     `plan_state`: `(user_id, next_template_id)`. `session_progress`: `(user_id, template_id)`,
     CASCADE. (SQLite doesn't check a composite key with a null part, so an extra still works.)
2. **Data**: `UPDATE ... SET user_id = 1` on the three tables. The owner is user 1 everywhere
   (`users.OWNER`, the ownership migration `c8b760ed9e52`, `link_owner` recreating id 1), so the
   migration first checks that user 1 exists, and the check in step 3 counts users other than 1:
   one definition of the owner for both.
3. **Other people** (members; the switch is off, and the Pi has none, checked 5 Nov 2026):
   **refuse** (Liam, 5 Nov 2026). The migration fails with a clear message if any user but the
   owner exists. Nobody is given a copy of the owner's plan: a new person starts from a starter
   (the seed's job, below) and finds their own level at setup. Check first, read-only:
   `SELECT count(*) FROM users WHERE id != 1`.
4. **Downgrade**: refuse while any non-owner plan rows exist; otherwise drop the columns and keys
   and restore the single-column uniques. The owner's rows become the shared plan again.
5. **Models and code in the same PR**: the three models inherit `Owned`; `version_on` takes the
   person; `build_plan_view` and `plan_coverage` read the person's rows; erase copies a starter;
   the export moves the tables; `test_user_scope` lists them.

**The seed's new job.** Catalogue only: exercises, ladder steps, tests, stretches, mobility, with
today's guards (no shortened ladder, renames by entry), plus a new one: no exercise any person's
items use (`all_users`) may be dropped. For a person with no sessions (a new member, an erased
person) it copies the first starter, sessions and versions, into their rows, with `exercise_state`,
`settings` and `plan_state` as today. It never touches a person who has sessions. The owner's
plan changes from `plan.toml` come through the import instead (`POST /api/plan/import`: the
plan as a pending change to review and save, Decided 1), which ships with step 5. The import is
the owner's alone: anyone else is refused (Liam, 5 Nov 2026).

**Before and after on the Pi** (backup-restore.md, "Rehearsal"; last run 2026-11-02):

1. Read-only first (`tc-read`): users, `plan_state` rows, open `session_progress` rows, and
   queue events inside the 24-hour undo window.
2. `training-coach backup` by hand before the release.
3. Drill, before the release PR is merged, so no tag exists and the deploy timer has nothing to
   take: a scratch clone at the release commit, `docker build -t training-coach:drill`, and the
   backup restored into `tc-drill` with that image; the migration and seed run on start. Pass
   when: row counts per plan table match, every `user_id` is 1, `PRAGMA foreign_key_check` is
   clean, the logs have no `seed.failed`, the import's diff is empty, and the owner's
   `/api/session/today`, `/api/progress`, `/api/review` and the export match the old image's
   answers on the same copy. Then `alembic downgrade -1` on a second copy and compare it with
   the backup.
4. A dry run is on a copy only: services commit inside, so a rollback is not a dry run.
5. Release at a quiet time, with no guided session in progress.

## Review (6 Nov 2026): what the plan was missing

A plan-critic read the plan against the code at 1.17.0. The migration holds; these change it.

**Erase.** Sessions and versions cascade from `users`, while `workouts` and `plan_state` RESTRICT
them, and SQLite's RESTRICT fires at once, even inside a cascade. So erase deletes the person's
`plan_state` and `workouts` first, then the user. A test erases someone with a logged workout.

**The seed's guards.** After the flip, on every start:

- `_versions_preflight` and the session-removal check go: the seed no longer touches either, and
  the first saved version would otherwise fail every start, unseen (the Dockerfile's `|| true`).
- New, against every person's stored items: an exercise they use must stay in the catalogue and
  not be retired, and an away item's steps must stay within what `_away_needs_no_kit` allows.
- A difference between the owner's rows and `plan.toml` stays until the owner saves it: the Plan
  page shows it, with the import.

**A new person's versions.** `plan.toml` had no starters then, so the 7-day cycle was the first
starter (since 8 Nov 2026 a new person starts on `new_people`'s starter, ADR-0073's addendum). Its
`[[versions]]` are the owner's history, so a new person gets one version, "Starting
plan", dated as the latest of them, so a past day they log still has one.

**The import** (`GET` and `POST /api/plan/import`, the owner's alone, anyone else refused):

- `GET` lists what would change: sessions added, reordered, removed or put back, and each
  version's items. Empty when
  the owner's rows match `plan.toml`.
- `POST` saves it as one version dated today, named after the latest `[[versions]]` entry. A
  second import that day updates that version, as `(user_id, since)` is unique.
- Workouts keep the version they have: only the seed's old bulk UPDATE re-stamped them, and a bound
  session refuses one. A workout logged earlier today did the old plan, so that is right.
- A session in progress today refuses it (`session_progress.sets` holds item positions, which
  would shift): finish or discard the session first.
- A session in the owner's rows but not in `plan.toml` is removed on save, and a retired one the
  file has is put back (ADR-0093 Decided 14; this refused it until #722).

**Reads.** `/api/plan` and coverage read rows through a service (the API layer can't query
models). `/api/plan/coverage?place=away` keeps today's answer (the home version) when ported.
`TemplateItem.template` pins its join, as the collections do.

**Rollback.** The old image can't find the new revision, so it can't start on the migrated file:
going back means restoring the pre-deploy backup, which loses anything logged after it
(`deploy.md`, Rollback). Hence a quiet time, and step 1's read first.

## The build

Merging never touches the Pi; only a release does.

1. Tests only: migration tests pinned to named revisions, an erase with a logged workout.
2. `/api/plan` and coverage read rows (shared rows until the flip).
3. **The flip:** the migration, `Owned`, composite keys, `version_on` taking the person, the seed's
   split and new job and guards, erase, export. It can't be split: schema, models and seed land
   together.
4. The import, with a small card on the Plan page. No release between 3 and 4, so the owner can
   always change their plan.

Released in 1.18.0, 7 Nov 2026 (`docs/sessions/2026-11-07-plans-per-person.md`).

The open points below keep the numbers this list had when they were answered: 5 the flip, 6 the
import.

## Open points for review

- **The gap between steps 5 and 6.** After step 5 the seed no longer changes the owner's plan,
  and the import (`POST /api/plan/import`, Decided 1) was planned for step 6. Until it ships, the
  owner can't change their plan at all. Ship the import with 5, or keep an owner-only seed path
  until 6? **Answered (Liam, 1 Nov 2026):** step 5 starts from about 4 Nov and the import ships
  with it, in the same release as the migration, so there is no gap where the owner can't change
  their plan. No owner-only seed path. Step 6 keeps the edits in the app.
- **Starters**: kept only in `plan.toml` and copied straight from it (no starter tables), or
  stored? **Answered (Liam, 6 Nov 2026):** `plan.toml`, as ADR-0073 says.
- **Refuse or copy** for members in the migration. **Answered (Liam, 5 Nov 2026):** refuse
  (step 3 above), and the import is the owner's alone.
- **Plan versions per person**: ADR-0073 adds "a short what changed" to each version. **Answered
  (Liam, 6 Nov 2026):** today's `name` holds it, and people manage their own plans. A change made
  in the background (a release changing an exercise in someone's plan) tells them: a notice,
  built after the import, with its own ADR.
