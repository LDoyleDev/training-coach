# ADR-0086: Away, no equipment: a third place with a written version of every session

- Status: Accepted
- Date: 2026-11-01
- Deciders: Liam

## Context

On 1 Nov 2026 Liam asked (#537): "We need a no-equipment option for any given day also. So that
when I'm in a hotel room I can still do a session."

ADR-0071 gave each session a home and a gym version (`template_items.place`), a Home | Gym switch
on Today for someone who trains at both, and steps that lock by the home kit. Its Decided 10 said
"no away place: travelling is Home with whatever is there". That doesn't answer the request: at
home the Legs session starts with kettlebell swings and the Torso session with pull-ups, and
the kit locks only steer Move up, not the step a session trains. A hotel room has a floor, a
chair, a bed, a wall, a door frame and a towel, and nothing else.

Sessions are still one shared plan until builder step 5 (ADR-0073), so a third version lives in
`plan.toml` like the gym ones. A shorter day (ADR-0082) and the preferences that lock steps
(ADR-0083) have to work on an away day as on any other.

## Decision

- **A third place, `away` ("Away, no equipment").** Today's switch offers it next to the day's
  other places for every session that has an away version: Home | Gym | Away for someone at
  both, Home | Away (or Gym | Away) for someone at one place. It amends ADR-0071 Decided 10.
- **An away day is an exception.** Choosing Away works like the gym switch: it is kept on the
  day's guided-session progress (`session_progress.place`) and on the saved workout
  (`workouts.place`), and can change until the first set is kept (after that it asks, and drops
  the kept sets, as ADR-0071's switch does). It never changes the person's places setting or the
  place Today starts at (`settings.place`): tomorrow starts where it would have. Every reader of
  the day's session that knows the day (the guided session, the bot's /today and its Start
  button, a typed or spoken log, logging a past day) sees the away version once it's chosen.
- **Written away versions,** `away = [...]` on each session in `plan.toml`, like the gym
  versions: reviewable and never generated. Only bodyweight and what any hotel room has: the
  floor, a chair, a bed, a wall, a door frame, a towel. No bands, kettlebells, bars or backpack.
  Each keeps its session's intent: the same muscles, roughly the same number of sets and time.
  The same exercise where it has a step that needs no kit (its history continues); a kit-free
  exercise in place of the rest. An exercise the catalogue lacks is added as an entry exercise
  with levels, marks, cues, questions and a figure (ADR-0063, ADR-0083).
- **The seed holds the rule:** every exercise in an away version has a bottom step that needs no
  kit and takes no load, and none of its steps takes a gym load (a barbell or a machine), so an
  away session always has a step it can train.
- **The step trained away:** each exercise trains at the person's level if that step needs no
  kit and takes no load; otherwise at the highest step below it that needs none. It is the
  kit-lock rule with an empty kit (ADR-0071), for today only: the person's level never changes,
  the sets are filed at the step done (ADR-0080's "for today", without a choice to store), and
  the set screen says "No-equipment step today". In a strength block the step a strength session
  would train (one up, ADR-0028) is the one checked. A level picked in the session (ADR-0080)
  is done as picked; the picker shows steps that need kit as locked. When the preferences land
  (ADR-0083, #531), a step the person avoids is passed over the same way.
- **Everything else as on any day.** Short on time today trims the away version by the same
  rules (ADR-0082), with its own "usually" per place. The bot names the place on /today and the
  Start button's detail ("Away, no equipment") and which exercises are at a no-equipment step.
  After an away workout, Move up still respects the home kit (a lasting change is about home).
- **What stays the home plan's:** the Plan tab, the body map and the week's cardio targets count
  the home and gym versions as before; an away day is an exception, not a plan.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A third place with written versions (chosen) | Reviewable sessions that keep each day's intent; levels and history carry over where the exercise is the same | A third version of every session to keep in the seed |
| Home with an empty kit (Decided 10 as it stood) | No new version | The kit locks don't change a session's exercises: swings and pull-ups stay in it |
| Generate an away version from the home one, swapping each kit exercise for a kit-free one by pattern | Nothing to write | Swaps nobody reviewed; patterns don't keep the muscles (a row has no kit-free twin) |
| Store "away" as a setting for a date range (travelling until ...) | One choice for a trip | A second place to read the day's place from; nobody asked for trips yet |

## Consequences

- `Place` gains `away`; the check constraints on `template_items`, `workouts` and
  `session_progress` allow it (a migration; downgrade refuses while a workout or progress row is
  away, and drops the away versions, which the seed writes). `settings.place` stays home or gym.
- `SessionTemplate.away_items` is the away version; `version(Place.AWAY)` falls back to the home
  version and `done_at` to home for a session without one, as for the gym.
- The guided view lists the places on offer (`places`) and marks each item trained at a
  no-equipment step (`no_kit`); the bot's texts gain the place line.
- The away versions and their reasons are in the PR that adds them, for Liam's review; new
  entry exercises need their figures before they're offered (ADR-0063).
