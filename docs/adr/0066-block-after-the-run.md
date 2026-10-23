# ADR-0066: A block after a cardio session's run stays open that day

- Status: Accepted
- Date: 2026-10-23
- Deciders: Liam

## Context

The core and hips block goes after the moderate cardio (`docs/specs/program-builder.md` K,
`docs/specs/program-builder-research.md`, Core and hips). A conditioning session could already
hold strength items in `plan.toml`, the guided session and the time estimate, but two things
stopped a block after the run from working:

- the run's one-step log (the web's cardio card, a counted band workout) saw a session with more
  than one item as no planned cardio, so it filed the run as an extra and the session stayed
  queued with the run in it;
- once the day's planned session is logged, however, `workout_log.target` returns None and every
  later log is an extra (ADR-0014), so the block after the run was neither guided nor saved with
  the session.

## Decision

- **The run is the session's cardio.** A conditioning session with exactly one cardio exercise
  (zone 2, moderate, HIIT) is today's planned cardio whatever else it holds (`cardio.planned`):
  the web's cardio card, a counted band workout, a typed or Telegram log ("run 35 min") and
  the guided session all log it as that session, and the queue moves then, once.
- **The rest stays open until the day ends.** Once a conditioning session's workout for today is
  saved with its cardio in it, `guided.today` offers its items not yet logged in that workout,
  its cardio left out, marked `after_run` ("After your run"). A conditioning session without
  exactly one cardio exercise, or saved without it, offers nothing after. Cardio-only days are
  done as before.
- **Its sets join the day's workout** (`workout_log.add_to`): it is the same session, so nothing
  clashes (ADR-0060) and the queue doesn't move again. Its ladders move from those sets like
  any session's. A repeated save adds nothing: the progress row says it's saved, the block's
  exercises are already in the workout, or, for two saves racing, a set's uniqueness in its
  workout rolls the second back.
- **Its own progress.** The guided progress row is marked `after_run`; the run's progress (saved
  or not) gives way to it when the block starts, and it is dropped if the run's log is undone.
  It is saved only on its day: the next day it isn't offered, since its day's session is logged.
- **The web page logs the run first.** A cardio day with a block shows the cardio card with
  "After your run: …", and after the run is logged the page opens the block.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Add the block's sets to the day's workout (chosen) | One workout per day; no clash, no second queue move; ladders, review and coverage read it as the session | A guided row needs a flag (`session_progress.after_run`); /undo of the day takes the run and the block together |
| Save the block as an extra workout | No schema change | Two workouts for one session; the block isn't the session's in the review, and extras never complete anything |
| Keep `target` on the session until every item is logged | One rule for all logs | Every typed log after the run would be checked against the session, and a day's session would count as done or not by what's left: the queue, clashes and the morning message all read `target` |

## Consequences

- A typed or Telegram log of the block's exercises after the run is still an extra (ADR-0014):
  its sets count and move ladders, but the guided block is the way to save them with the
  session.
- /undo of the run (`workout.logged`) takes the whole day's workout, block included; adding the
  block (`workout.added`) has no undo of its own.
- The home button reads "<session>, after your run" with the block's minutes, and no "usually"
  time (that is the whole session's).
- Tests: `tests/services/test_after_run.py`, `tests/api/test_after_run_api.py` and the session
  page's run-then-block tests.
