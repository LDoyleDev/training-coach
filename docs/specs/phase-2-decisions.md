# Phase 2: decisions on blocks, overload, retests, the weekly review, photos and habits

Status: **all decided by Liam on 2026-10-07**, including the overload step size (section 1),
photo storage (D3) and habits (D5). The table of decisions stays in `phase-2-overview.md`; only
D1 (dashboard design) is still open there.

## 1. Progressive overload: how big a step (decided, ADR-0027)

**Liam's direction:** every session's target should be a little more than last time, "a couple
of reps" per set, not ADR-0016's +1.

**Why not a flat +2.** Exercises have very different ranges in this plan. +2 is a lot for 4 sets
of 5-12 pull-ups (a 20% jump on 10 reps every week, so most sets would miss and the target
would stop meaning anything), and little for 15-25 tibialis raises. "Double progression" (add
reps inside a range, then make the exercise harder) works best with small, regular steps you
actually hit. Each exercise here comes round about once a week, so a step is one week's progress.

**Decided: step about 10% of the top of the range (halves round up), at least 1.**

| Range (top) | Step per set | Example: last session | Next target |
| --- | --- | --- | --- |
| 4-8 (strength block) | +1 | 6 / 6 / 5 | 7 / 7 / 6 |
| 5-12 | +1 | 8 / 7 / 6 / 5 | 9 / 8 / 7 / 6 |
| 8-15 | +2 | 10 / 9 / 8 | 12 / 11 / 10 |
| 15-25 | +3 | 18 / 16 / 15 | 21 / 19 / 18 |
| Timed, 20-60 s | +5 s (10%, rounded to 5 s) | 40 / 35 s | 45 / 40 s |
| Duration, 30-40 min (cardio) | +1 min until heart-rate zone data arrives | 32 min | 33 min |

Rules around the step:
- **Per set, from what you did.** Each set's target is that set's last value plus the step, never
  above the top of the range. This replaces ADR-0016's "weaker sets catch up to the best"; with a
  bigger step that rule over-reached.
- **A miss holds the target.** If a set fell short of its target, the next target is the same as
  the one missed (it doesn't climb from the lower number, and doesn't run away either).
- **No history:** bottom of the range, as now.
- **Moving up is unchanged** (only ADR-0016's target rule is replaced, not its progression
  rule): every set at the top of the range in two sessions in a row, then
  Move up / Not yet (ADR-0016, ADR-0025). Bigger steps simply get you there sooner.
- **Pace setting (optional, later):** "steady" (+1 everywhere), "standard" (the table above,
  the default), "fast" (+2 minimum). Worth having once other people use the app.

Recorded in ADR-0027, which supersedes ADR-0016's target rules. Code: `domain/targets.py` and its
table-driven tests (pure code, 100% covered).

## 2. Training blocks (D2): decided (ADR-0028)

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

## 5. Progress photos (D3): decided 2026-10-07

- Stored on the Pi for now, next to the database, readable only by the app's user and group
  (as the backups are, ADR-0024). Where, or whether, to store them is decided again when the
  app moves to another server.
- Never in logs, share views (ADR-0012) or public endpoints (ADR-0019).
- The nightly backup and the desktop pull include them (today they copy the database only).

## 6. Habits (D5): decided 2026-10-07

- **Three one-tap check-offs**, in one evening message (sent in place of the nudge when
  nothing else is due):
  - **Morning light:** outside within an hour of waking, about 10 minutes when clear and
    20-30 when cloudy.
  - **Protein target:** a daily protein goal reached; the number is a setting.
  - **Wind-down:** no screens or bright light in the last hour before bed.
- **Two that track themselves** once the band's data arrives (health data phase): sleep
  regularity (in bed and up within about 30 minutes of the usual times) and daily steps.
- Left out on purpose: caffeine timing (a fourth daily tap), cold and heat (part of the
  Recovery session instead), hydration.
- The weekly review shows each habit's week ("5 of 7"); there are no streaks to break.

## Next

ADR-0028 records the blocks; the phase 2 issues are open in milestone "Phase 2 - Overview".
D1 (the dashboard) is being decided with a clickable mockup.
