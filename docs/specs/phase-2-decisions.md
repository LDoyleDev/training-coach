# Phase 2: options for the open decisions

Status: **proposal, waiting on Liam.** Covers D2, D4 and D6 from `phase-2-overview.md` (the
table of open decisions stays there; this file holds the options). D1 (dashboard design), D3
(photo storage) and D5 (habits) are better settled together at the desktop. Each section ends
with a recommendation; answer with the letter, or change anything.

## D2: Monthly strength and hypertrophy blocks (#26)

**Background.** Huberman alternates monthly between strength (4-8 reps, 3-4 sets, 2-4 min rest)
and hypertrophy (8-15 reps, 2-3 sets, about 90 s rest). The app runs hypertrophy ranges only.
With bodyweight work, "heavier" means a harder ladder step, not more load.

**Questions inside this decision**
1. How long is a block, and when does it start?
2. What changes in a strength block: the step, the rep range, the sets, the rest?
3. How do targets and "ready to progress" count across blocks?
4. Is there a lighter (deload) week between blocks?

### Options

| | A. Calendar months | B. 4-week blocks from a start date | C. Rep ranges only |
| --- | --- | --- | --- |
| Block length | Flips on the 1st of each month | 4 weeks from a date you pick; the count stops while the bot is paused | 4 weeks |
| Strength block | One ladder step harder, 4-8 reps, sets as planned | Same as A | Same step, 4-8 reps (slower tempo or pauses for difficulty) |
| Hypertrophy block | Current step, the planned ranges (8-15 mostly) | Same as A | Same as A |
| Targets and progression | Kept separately per step and block kind | Same as A | Kept per step and rep range |
| Effort to build | Medium | Medium | Small |
| Catch | Months are 28-31 days; a holiday or illness eats the block | Needs a "pause the block" rule for missed weeks | Strength work at the same step is barely stronger; misses the point of the block |

Notes that apply to A and B:
- **Strength step.** "One step harder" uses the next ladder step. At the top of a ladder, the
  strength block keeps the top step and adds a tempo or pause cue (the plan has no harder
  variation to use).
- **Where progression lives.** Move up is offered only in hypertrophy blocks, for the step you
  train there. Strength blocks set personal bests and give the next hypertrophy block a head
  start, but don't move you up on their own. This keeps ADR-0016's rule unchanged.
- **Targets.** Each block kind keeps its own history per step, so a strength block's 5-rep sets
  never become the target for the next hypertrophy block's 12-rep sets.
- **Warm-up.** The morning message before every resistance session adds "~10 min warm-up first"
  with the session's warm-up (from the plan), in both block kinds.
- **Deload.** Huberman's protocol has no explicit deload. A simple option is the last 3 days of
  each block at 2 sets instead of the planned number. Off by default.

**Recommendation: B** (4-week blocks from a start date, starting with hypertrophy), no deload
for now, and "a block pauses while the bot is paused". A bad week then never cuts a block short.
It needs one new ADR (it amends ADR-0016's target rule) and one small migration (block kind on
workouts).

## D4: Retest cadence

**Background.** The product spec lists two days of baseline tests (day 1: bodyweight, girths,
photos, resting heart rate, max pull-ups/push-ups/dips, dead hang; day 2: split squats, goblet
squat, calf raises, 12-minute run, deep squat hold, toe touch) and says retest every 4-6 weeks
under the same conditions.

### Options

| | A. Fixed every N weeks | B. At every block boundary | C. Every other block boundary |
| --- | --- | --- | --- |
| Cadence | 4, 5 or 6 weeks from the baseline | Every 4 weeks (with D2-B) | Every 8 weeks |
| How it fits the queue | Two test days inserted when due | The first two days of each new block are test days | The first two days of each hypertrophy block |
| Pros | Simple, independent of blocks | Before/after numbers for every block | Less testing time; still 6+ results a year |
| Cons | Can land mid-block, testing tired or fresh by chance | 2 of every 28 days are tests (7%) | Outside the spec's 4-6 weeks |

Notes:
- Test days are inserted into the queue (ADR-0006), so the training order is kept and
  everything shifts by two days; "Rest today" and "Swap" work on them as on any session.
- "Same conditions": the bot asks the same questions each time (time of day, fed or fasted,
  slept well) and shows them next to the results, rather than refusing to record a test.
- The dashboard compares each result with the baseline and the previous retest.

**Recommendation: B** if you choose D2-B (retest at the start of every block, so every block has
a before and after), otherwise **A every 6 weeks**.

## D6: Weekly review day and time

**Background.** The product spec says Sunday. The review covers sessions done vs planned, hard
sets per muscle group vs Galpin's 10-20, personal bests and what is ready to progress (2-C).
Once wearable data exists (see `platform-and-health-data-proposal.md`) it can add zone 2
minutes, steps and sleep regularity.

### Options

| | A. Sunday evening | B. Monday morning | C. Configurable |
| --- | --- | --- | --- |
| When | Sun 18:00 | Folded into Monday's morning message | `/settings`, default Sun 18:00 |
| Pros | The week is over; time to think about next week | One message instead of two | Fits any routine |
| Cons | Sunday is the long zone 2 day; if logged late, the review misses it | Long morning message on a training day | One more setting |

Notes:
- The week is Monday to Sunday in Europe/Berlin.
- Skipped while the bot is paused; sent even when nothing was logged ("0 of 7 sessions").
- A late log for the week (after the review) does not resend it; `/review` shows the current one
  any time.

**Recommendation: C**, defaulting to Sunday 19:00 (after an afternoon zone 2 session), plus a
`/review` command.

## Your answers

Reply with a letter per decision (for example "D2 B, D4 B, D6 C") and anything you'd change. I
then write the ADRs, update `phase-2-overview.md`, and open the issues.
