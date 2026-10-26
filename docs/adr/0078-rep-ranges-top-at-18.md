# ADR-0078: A rep range tops out at 18; high-rep work keeps its range

- Status: Accepted
- Date: 2026-10-26
- Deciders: Liam

## Context

Liam (26 Oct 2026): "Once we get to 18 repetitions on something, we should be thinking about
what's the next step up."

Five exercises in the plan asked for up to 20 reps: push-up 10-20, one-arm kettlebell row 10-20,
kettlebell curl 12-20, lateral raise 12-20 and rear-delt reverse fly 12-20. The ready rule
(every planned set at the top of the range in two sessions in a row, ADR-0016, with targets
stepping towards the top, ADR-0027) only offered Move up at 20, so those sets kept climbing
inside one level long after the next level was the better step.

Four others are high-rep work on purpose: single-leg calf raise 12-20, tibialis raise 15-25,
kettlebell swing 15-20 and band face pull 12-20. Timed work (dead hang, carries, cardio
minutes) is counted in seconds or minutes, not reps.

When the rule is met there may be no level to move to: the ladder ends, or the next level needs
kit the person hasn't listed (ADR-0071). Progress and the Plan tab's levels already said "top for
your kit" and named the kit that would open the next level; the screen after saving a session
and the bot's /progress didn't.

## Decision

1. **18 is the top.** Every range counted in reps whose top was above 18 stops at 18; the bottom
   stays. Targets never ask for more than 18, and the existing ready rule then offers Move up at
   18. There is no new ready rule.
2. **High-rep work keeps its range:** calf raise, tibialis raise, kettlebell swing and band face
   pull. Exercises counted in seconds or minutes are not affected.
3. **The change is its own plan version**, "Rep tops at 18", from 2026-10-27 (ADR-0034).
   Readiness and targets are judged against the plan as it is now, as before: a session logged
   under the old range with every set at 18 or more counts as at the top. Personal bests are
   raw values and don't change.
4. **No level to move to says so.** When the rule is met on the last level, the saved screen
   says "top of the range on the last level of its ladder". When the next level needs kit that
   isn't listed, it says "top of the range on the last level your kit allows" and what would
   open it ("An 8 kg kettlebell unlocks Holding 8 kg"), linking to My equipment; /progress in
   Telegram names it too. Like the bot's note, it is said once per level. Nothing moves anyone:
   the person decides.
5. **A test holds the plan to this:** every reps range in the bundled plan tops out at 18 or
   lower unless its exercise is in the named high-rep set, so a later plan edit can't break it
   silently.

Adding load where a ladder simply ends is builder step 8 (ADR-0072), not this decision.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Cap tops at 18, four named high-rep exceptions (chosen) | One number to remember; the ready rule is unchanged | The exceptions are a list to keep up to date |
| A new ready rule: 18 on any set offers Move up | Ranges stay as written | Two rules for one question; weaker sets would never reach the top |
| Leave the ranges at 20 | Nothing to change | Sets keep climbing in one level when the next one is the better step |

## Consequences

- `plan.toml`: push-up 10-18, kettlebell row 10-18, kettlebell curl 12-18, lateral raise 12-18,
  reverse fly 12-18, and a new version dated 2026-10-27. The seed updates the ranges in place and
  never resets progress.
- Someone who already did 18 or more on every set in their last two sessions at a level is
  offered Move up on their next save, and Progress shows it ready at once.
- `tests/services/test_seed.py` names the high-rep set; adding an exercise to it is a decision,
  not a test fix.
- The saved view (`EarnedView`) gains `at_top` and `unlock`; the API types are regenerated.
- Home and the weekly review still list only exercises ready to move up; the top of a ladder
  shows on Progress, the Plan tab's levels, the saved screen and the bot.
