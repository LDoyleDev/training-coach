# ADR-0016: Queue edge cases and target rules

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

Step 1-C turns ADR-0006 and the product spec into code. A few cases were not decided yet.

## Decision

**Queue**
- Only completing the session *at the pointer* with `done` or `rest` moves the pointer, by
  exactly one. Doing a different planned session (out of order) is logged but does not move
  the pointer; the session you skipped over stays next. A deliberate swap will be an explicit
  "Swap" action in the bot (step 1-D), not an implicit side effect.
- Two planned sessions in one day advance twice (ADR-0014). Logging the same session twice
  advances once.
- Calendar dates are computed from aware UTC moments in Europe/Berlin (`local_date`).

**Targets** (per set, from the last session at the same ladder step)
- All sets equal: +1 on every set. Otherwise +1 on every set below the best, up to the best.
- Never above the top of the range. Below the bottom of the range, targets still grow one rep
  at a time (no jump to the minimum). No history: bottom of the range.
- Fewer sets logged than planned: the missing sets start from the weakest logged set.

**Progression**
- Ready when every planned set is at or above the top of the range in each of the last two
  sessions at the current step. Unilateral sets count the weaker side and need both sides; a
  missing set or side counts as 0, so gaps never trigger progression. At the last ladder
  step the result is `top_of_ladder` instead of `ready`.

## Consequences

- All of this is pure code in `domain/`, held at 100% test coverage by CI, and guarded
  against framework imports by a test.
- Changing a rule later means a new ADR and table-driven test updates.
