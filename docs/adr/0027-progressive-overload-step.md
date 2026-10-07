# ADR-0027: Progressive overload step of about 10% of the range

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam
- Supersedes: ADR-0016's **Targets** rules (its queue and progression rules still apply)

## Context

ADR-0016 aims +1 rep on every set (or brings weaker sets up to the best). Liam wants each
session to ask for more than that, "a couple of reps" per set. A flat +2 suits high-rep work but
is a 20% weekly jump for 5-12 pull-ups, so most sets would miss. Options and examples:
`docs/specs/phase-2-decisions.md`, section 1.

## Decision

Targets per set, from the last session at the same ladder step (and, once blocks exist, the same
block kind):

- **Step:** 10% of the top of the range, halves rounding up, at least 1. 4-8 and 5-12 give +1,
  8-15 gives +2, 15-25 gives +3. Timed exercises round to 5 s steps (at least 5 s); duration
  (minutes) exercises use +1 minute.
- **Per set:** each set's target is that set's last value plus the step, never above the top of
  the range. Weaker sets no longer jump to the best set.
- **A miss holds the target:** if a set fell short of the target it was given, its next target is
  that same target, not a step from the lower number. Missed or not is judged per set.
  - "The target it was given" is recomputed, so nothing new is stored: it is the target rule
    applied to the session before it at the same ladder step (and, once blocks exist, the same
    block kind).
  - **The first session at a step is the baseline:** it is never a miss, and the next targets
    step up from what was done. So below the bottom of the range targets grow by the step
    instead of jumping to the minimum.
  - **Two misses in a row** of the same set at the same held target: the next target for that
    set is its last value plus 1, so a bad patch (illness, poor sleep) never leaves a target
    out of reach for good.
- **Unchanged from ADR-0016:** no history means the bottom of the range; below the bottom,
  targets grow gradually (here by the step, from the baseline above) rather than jumping to the
  minimum; fewer sets logged than planned start the missing sets from the weakest logged set.

## Consequences

- Implemented in `domain/targets.py` (#70): the targets each past session was given are replayed
  from the oldest session at the step, so the rule needs nothing stored beyond the logged sets.
- `domain/targets.py` changes; it stays pure and at 100% coverage, with the table-driven tests
  rewritten for the new rule.
- Exercises reach the top of their range sooner, so the progression prompt (ADR-0016, ADR-0025)
  comes earlier; its rule is unchanged.
- A pace setting (steady +1, standard as above, fast with at least +2) is left for later.
- History is every session at the step, whichever planned session it was logged in, judged
  against today's prescription. An exercise with different ranges in two sessions can see a
  target held or eased against the "other" range; blocks will add the block kind to the scope.
