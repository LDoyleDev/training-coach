# ADR-0025: Personal bests and the "ready to progress" prompt

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam

## Context

Step 1-G gives feedback after a save. ADR-0016 already fixes when an exercise is ready to move
up. Still open: what counts as a personal best, which prescription a log is judged against,
how often the prompt repeats, and what happens at the top of a ladder.

## Decision

- **Personal bests** are kept per exercise and ladder step: the best single set and the best
  session total, from the same per-set values as progression (weaker side for unilateral work,
  a missing set as 0). A record is announced only when it beats every earlier session at that
  step, so the first session at a step, including right after moving up, is never a "best".
- **Prescription**: a log is judged against the logged session's range; an extra session, or an
  exercise that session doesn't list, uses the plan's first session with that exercise.
  Progression is only assessed for the step being trained now; a log at an older step only
  counts for bests.
- **Prompt**: after a save that meets the rule, "Move up" / "Not yet" buttons per exercise.
  Buttons carry only the exercise and step ids. "Move up" checks again on press (still on that
  step, still ready under one of the exercise's prescriptions, a next step exists) and only
  then moves; a stale or forged press changes nothing. "Not yet" is recorded as an event, and
  the prompt returns after the next save that still meets the rule.
- **Top of the ladder**: when the rule is met on the last step, the owner is told once per
  exercise and step (an event records it) to add a harder variation to `plan.toml`.

## Consequences

- Moving up resets targets to the bottom of the range for free: the new step has no history.
- Bests and prompts are computed from the logs on every save; nothing new is stored except
  events, so a plan or rule change never leaves stale records behind.
- Changing these rules later needs a new ADR and table-driven test updates.
