# ADR-0032: Stretching after a resistance session is chosen for the muscles worked

- Status: Accepted
- Date: 2026-10-08
- Deciders: Liam (#98: 10, 20 or 30 minutes)

## Context

Liam wants to add stretching to the end of a resistance session by choosing how much time to
spend, with the system choosing the routine. The plan had one stretch, a fixed 10-minute
mobility flow on the Recovery day.

## Decision

- **Stretches** live in `plan.toml` (`[[stretches]]`): name, the muscle groups each one
  stretches (the exercises' own names, checked by the seed so a typo can't quietly never
  match), one-sided or not, and a cue. No equipment beyond a wall, door or chair.
- **Dose** (Huberman Lab, the flexibility episode): static holds of 30 s at a gentle effort
  (3-4 out of 10), 2 or 3 rounds. Time per stretch is rounds × sides × (30 s hold + 10 s to
  change position).
- **Choice** (`domain/stretching.py`), filling the chosen 10, 20 or 30 minutes without going
  over:
  1. two rounds of a stretch for each muscle the session worked, most planned sets first,
     skipping stretches whose worked muscles are already covered;
  2. a third round of those, in the same order;
  3. two rounds of stretches for the rest of the body.
- The stretches are read from the bundled plan file, not stored: nothing logged refers to a
  stretch (as `/api/plan` already reads the file, ADR-0019).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Chosen per session from a catalogue (chosen) | Fits the time; follows what was trained | A catalogue to maintain |
| Fixed routines per session and length | Simple to read and edit | 9 routines to keep in step with the plan |
| Whole-body routine regardless of session | Simplest | Ignores what was trained, which matters most at 10 minutes |

## Consequences

- At 10 minutes the routine covers 3-4 of the session's muscles; longer choices add third
  rounds before the rest of the body.
- Adding a stretch is a plan edit; the selection picks it up without code changes.
- Showing and logging the routine (buttons, the Done button) is the second half of #98.
