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
- The "Saved" reply to a resistance log offers Stretch 10 / 20 / 30 min. A choice sends the
  routine with a Done button, and Done logs the minutes on that workout as the plan's mobility
  exercise. That is one per workout, so a second tap can't double it.

## Addendum (2026-10-25): guided stretching, the chosen minutes as the real total

Liam asked for an overview of what's coming, then a timed routine he follows by the bells
alone: time to get into each stretch, the hold counted down, a bell at each change. The
choice of stretches above stands; the timing and the web page change.

- **Timing.** 15 s to get into position before each stretch and before its other side; 5 s
  to let go between rounds on the same side; a one-sided stretch does all its rounds on one
  side, then the other. A stretch takes sides × (15 + rounds × 30 + (rounds − 1) × 5) s,
  replacing the flat 10 s per hold.
- **The chosen 10, 20 or 30 minutes are the real total**, gaps included. The routine still
  fills them without going over, so it never needs fewer than two rounds of a stretch; when
  time runs short the least important stretches are the ones left out. Against the bundled
  catalogue every strength session's routine comes within a minute of the choice
  (`tests/services/test_stretching.py`).
- **Web.** Choosing a time shows the overview: the stretches in order with hold, rounds and
  sides, and the true total. Start runs the guided player (`StretchPlayer.tsx`), built on the
  mobility flow's pure clock (`session/flow.ts`, ADR-0062): each position, hold and release is
  a section of one timeline, so countdowns, Back and Skip, "Next: …" over a stretch's last 5 s
  and the sounds use the same functions. The person's Sound from Settings plays at every change
  (a new stretch and a hold: next; the other side: switch; letting go: count; the end: finish),
  with a buzz where the phone has one, never on tapping Start. The screen stays on; pause, Back
  and Skip work as in the flow. The stretch's figure shows while getting into position, when
  there is one.
- **Logging.** Run to the end, the player logs the minutes it actually ran by itself (whole
  minutes, never more than chosen). Stopped early, it offers to log the whole minutes done (at
  least 1) or nothing. The API accepts 1 to 30 minutes, no longer only a choice. "Done
  stretching" stays on the overview for stretching without the phone and logs the chosen time.
- The bot keeps its list and Done button; its routine uses the same timing.
