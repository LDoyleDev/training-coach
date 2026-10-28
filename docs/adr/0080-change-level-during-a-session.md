# ADR-0080: Change an exercise's level during a session, for today or from now on

- Status: Accepted
- Date: 2026-10-27
- Deciders: Liam

## Context

On 27 Oct Liam had a new 16 kg kettlebell and wanted to do that day's kettlebell swings at
"Two-hand, 16 kg", above his level. The guided session had no way to change a level: he had to
leave it and change the level on the Plan tab (ADR-0075). Sets are saved at each exercise's
current step at save time (`blocks.step_for` in `workout_log`), so a level changed halfway
through a session would also have moved the sets already done to the new step.

## Decision

- **"Change level" on the set screen** for every exercise with more than one step. It opens the
  exercise's ladder with one level down and one up first and "All levels" behind it, each step
  with its cue, locked steps said in words with the kit they need, and still choosable with the
  warning, as on the Plan tab (ADR-0071). The page gets the ladder with today's session
  (`items[].level`), so the picker works without another request.
- **Picking a level asks "For today" or "From now on".**
  - **From now on** is the Plan tab's by-hand change: the same service (`progress.set_level`), the
    same `progress.level_set` event and the same kit warning. It goes through
    `PUT /api/session/level` rather than ADR-0075's endpoint so that the sets already done are
    kept at their step in the same transaction.
  - **For today** changes this session only: the person's level stays. The chosen step is kept
    with the session's progress (`session_progress.steps`, exercise slug to step id), so a reload
    or another device shows it, and the save files that exercise's sets at it.
- **Either way the rest of today's sets are at the step picked**, with that step's own targets
  (ADR-0016, ADR-0027: no history at a step means the bottom of the range), its load if it takes
  one (ADR-0072), its cue and its figure. In a strength block a strength session trains one step
  above the level (ADR-0028); a level picked in the session is done as picked, without that extra
  step, for both answers. The level itself is what the person chose, so later strength sessions
  add the step again.
- **Sets already confirmed keep the step they were done at.** When the level changes, the server
  marks each confirmed set of that exercise with the step it was shown at (`step_id` in the kept
  set); the browser never sends a step, and a later keep keeps the mark. At save each set goes to
  its marked step, else the level chosen for today, else the current step. A step that is not on
  the exercise's ladder is ignored. So a session can hold sets of one exercise at two steps, and
  each counts in its own step's history: targets, bests, readiness and the Progress graph.
- **The saved screen says it:** each exercise whose level changed in the session is listed with
  the steps its sets were done at ("Kettlebell swing done at Two-hand, 8 kg, then Two-hand,
  16 kg."). The set screen marks a step chosen for today only ("for today only").
- **It works in any block**: a level by hand is the person's choice, not the rule's (ADR-0075).
- **Like a kept set, a change names the revision the browser saw** (`session_progress.revision`);
  a stale page is answered 409 and reloads instead of changing anything. Nothing asks before
  overwriting (ADR-0060) because nothing is overwritten: the sets done stay as they were.
- **Telegram is out of scope**: a typed or spoken log is filed at the current steps, as before.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| For today or from now on, sets done keep their step (chosen) | Honest history; a one-off heavier day doesn't move the level; the Plan tab's rules for a lasting change | A column and a mark per kept set; a session can save one exercise at two steps |
| From now on only, with the Plan tab's endpoint | No new storage | A one-off day changes the level; the sets already done move to the new step |
| For today moves every set of the exercise to the new step | Simpler save | Sets done at the old step would count in the new step's history and targets |

## Consequences

- A migration adds `session_progress.steps` (JSON, default `{}`); kept sets may carry `step_id`.
- `PUT /api/session/level` (owner-only) answers the new today view and any kit warning;
  `GET /api/session/today` items gain `level` (step id, for today only, ladder) and a saved
  session's answer gains `levels`.
- `workout_log.Draft` gains `steps`, the step of each set done at a level changed in the session;
  every other log is filed as before.
- "Ladder steps climbed" on Home still counts Move ups only (ADR-0075).
