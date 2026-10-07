# Phase 2: decisions on blocks, overload, retests and the weekly review

Status: **D2, D4 and D6 decided by Liam on 2026-10-07; the overload step size (section 1) is a
proposal waiting for a yes.** Becomes ADRs and issues once confirmed. The table of open
decisions stays in `phase-2-overview.md`; D1 (dashboard design), D3 (photo storage) and D5
(habits) are still open there.

## 1. Progressive overload: how big a step (proposal)

**Liam's direction:** every session's target should be a little more than last time, "a couple
of reps" per set, not ADR-0016's +1.

**Why not a flat +2.** Exercises have very different ranges in this plan. +2 is a lot for 4 sets
of 5-12 pull-ups (a 20% jump on 10 reps every week, so most sets would miss and the target
would stop meaning anything), and little for 15-25 tibialis raises. "Double progression" (add
reps inside a range, then make the exercise harder) works best with small, regular steps you
actually hit. Each exercise here comes round about once a week, so a step is one week's progress.

**Proposal: step about 10% of the top of the range (halves round up), at least 1.**

| Range (top) | Step per set | Example: last session | Next target |
| --- | --- | --- | --- |
| 4-8 (strength block) | +1 | 6 / 6 / 5 | 7 / 7 / 6 |
| 5-12 | +1 | 8 / 7 / 6 / 5 | 9 / 8 / 7 / 6 |
| 8-15 | +2 | 10 / 9 / 8 | 12 / 11 / 10 |
| 15-25 | +3 | 18 / 16 / 15 | 21 / 19 / 18 |
| Timed, 20-60 s | +5 s (10%, rounded to 5 s) | 40 / 35 s | 45 / 40 s |
| Duration, 30-40 min (cardio) | +1 min until zone data arrives (phase 3) | 32 min | 33 min |

Rules around the step:
- **Per set, from what you did.** Each set's target is that set's last value plus the step, never
  above the top of the range. This replaces ADR-0016's "weaker sets catch up to the best"; with a
  bigger step that rule over-reached.
- **A miss holds the target.** If a set fell short of its target, the next target is the same as
  the one missed (it doesn't climb from the lower number, and doesn't run away either).
- **No history:** bottom of the range, as now.
- **Moving up is unchanged:** every set at the top of the range in two sessions in a row, then
  Move up / Not yet (ADR-0016, ADR-0025). Bigger steps simply get you there sooner.
- **Pace setting (optional, later):** "steady" (+1 everywhere), "standard" (the table above,
  the default), "fast" (+2 minimum). Worth having once other people use the app.

Needs: a new ADR superseding ADR-0016's target rule, and table-driven test updates in
`domain/targets.py` (pure code, 100% covered).

## 2. Training blocks (D2): decided

- **Optional, per person.** A setting asks whether you train in blocks. Off by default; you'll
  turn it on.
- **When on:** 4-week blocks from a start date, alternating:
  - **Strength block:** lower reps, higher intensity. 4-8 reps, the next ladder step (harder
    variation), 3-4 sets. At the top of a ladder, the top step with a tempo or pause cue.
  - **Hypertrophy block:** more reps, less intensity. The plan's ranges at the current step.
- Targets are kept separately per block kind and step, so strength sets never become targets for
  hypertrophy sets. Move up is offered in hypertrophy blocks; strength blocks set bests.
- The count of block weeks stops while the bot is paused, so a lost week doesn't shorten a block.
- The morning message names the block and adds the ~10 min warm-up before resistance sessions
  (#26).
- No deload week for now.

## 3. Retests (D4): decided

- **With blocks:** at the start of each block, so every block has a before and after.
- **Without blocks:** every 4 weeks.
- Test days go into the queue like any session (ADR-0006): the order is kept and everything
  shifts by two days. The same short questions each time (time of day, fed or fasted, slept
  well) sit next to the results.

## 4. Weekly review (D6): decided

- **Sunday evening**, 19:00 by default (after the long zone 2 session), adjustable in `/settings`.
- Monday to Sunday in Europe/Berlin; skipped while paused; `/review` shows the current week at
  any time.

## Next

Once you confirm section 1: ADRs for overload and blocks, then `phase-2-overview.md` updated and
the phase 2 issues opened.
