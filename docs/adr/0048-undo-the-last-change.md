# ADR-0048: Undo the last change to the plan

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam

## Context

A mistaken tap (Rest today instead of Start) or a log saved with a wrong number had no way
back in the bot: sending `/undo` got no answer. The queue is a single pointer plus queued
sessions (ADR-0006, ADR-0022), and every change already writes an event.

## Decision

`/undo` takes back the last change of these kinds: a rest day, a push to tomorrow, a swap and
a saved workout log (typed, voice or guided).

- Each of those events records, beside its usual payload, `undo`: the queue before and after
  (`[pointer, queued]`) and the id of the workout row it added. Ids and positions only: no
  sets or measurements, as the event rule requires.
- `/undo` names the change and asks: **Undo it** / **Keep it**. A wrong tap is what this
  fixes, so it gets a confirm step too.
- It applies only while the queue is still where that change left it and its workout still
  exists. Otherwise it refuses ("something changed since"), rather than guessing.
- One step only, within 24 hours. After an undo there is nothing to undo until the next
  change; there is no redo (do the action again instead).
- Undoing a guided session's log keeps its sets: the session becomes unsaved again and can be
  saved again.
- Events written before this change carry no `undo` and are not undoable.

Habit ticks (each tap toggles) and settings (each shows its value) already undo themselves and
are left out. "Pick another session" changes nothing to undo.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Snapshot in the event, one step, guarded (chosen) | Small; no new table; can't clobber a later change | One step only |
| A full undo stack | Several steps back | Each step must re-check everything after it; easy to corrupt the queue |
| Recompute the queue from the workout history | No snapshots | The queue holds swaps that the history can't reproduce |

## Consequences

- `services/undo.py` owns the rule; `queue_actions` and `workout_log` add the `undo` record.
- A future web undo can call the same service.
