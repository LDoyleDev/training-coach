# ADR-0034: Plan changes keep history per exercise

- Status: Accepted (retired exercises; plan versions and the baseline label follow in #107)
- Date: 2026-10-09
- Deciders: Liam (#107)

## Context

The plan has changed once (ADR-0017) and will change again. The Pi was seeded with the new
plan, so exercises from the first week (goblet squat, reverse lunge) were never in its database
and that week couldn't be backfilled (ADR-0033). An exercise dropped from the plan also had no
way to leave `/progress`, and nothing marks when the plan changed.

## Decision

- **History follows the exercise, never the plan day.** Exercises are retired, never deleted.
- **Retired exercises** are marked `retired = true` in `plan.toml`, keeping their ladder, name,
  aliases and muscle groups; the seed stores the flag on `exercises.retired`. A plan that puts a
  retired exercise in a session is refused with a clear message. A retired exercise can say
  `per_side = true`, since no session item says how it's logged.
- **Where they show:**
  - Logging (typed, voice, past days): yes. They're in the parser's catalogue and the voice
    vocabulary, so old days can be backfilled.
  - Morning message, targets, progress prompts and Move up: no. They're in no session, so they
    have no prescription and are never ready.
  - `/progress`: only once they have history, labelled "(retired)".
  - Weekly volume and bests: yes. Volume counts by muscle group, as for any exercise.
- **No conversion between exercises.** Goblet squat reps say nothing reliable about jump squats
  or split squats. A new exercise starts from its own baseline, which takes one session.
- Still to come in #107: a plan version on every workout, and a "baseline" label on a new
  exercise's first prescription.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Retire in plan.toml (chosen) | Explicit and reviewed like any plan change; history kept | Retired entries stay in the file |
| Treat any exercise missing from plan.toml as retired | Nothing to mark | A typo or a bad merge would silently retire an exercise |
| Delete dropped exercises | A tidy plan | Destroys logged history (refused since 1-A) |
| Convert old results to the new exercise | Continuous charts | The numbers aren't comparable; it would invent progress |

## Consequences

- The first plan's goblet squat and reverse lunge are back in `plan.toml`, retired. The goblet
  squat's "squat"/"squats" aliases are dropped, so a casual "squats 10" can't land on an
  exercise that is no longer trained.
- Retiring an exercise later is one line in `plan.toml`, after taking it out of its sessions.
