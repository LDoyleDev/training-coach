# ADR-0067: A cardio log carries how hard it felt, and optionally distance, heart rate and start

- Status: Accepted
- Date: 2026-10-23
- Deciders: Liam

## Context

A cardio log saved minutes and what it was (walk, run...) and nothing else. A run recorded on a
watch or phone app shows much more: distance, pace, average and highest heart rate, a start
time, the vendor's own training load and recovery scores, cadence, calories, a route. Someone
logging that run by hand needs a short list of what is worth typing, and the list must work
for a person with no device at all and compare across devices.

Most of what an app shows is either already covered (steps), not used by any decision in the
coach (cadence, stride, splits), unreliable (calories) or a vendor score that can't be compared
across devices (Xiaomi's training load, recovery hours, vitality score). Heart-rate zones are
worth having, but each vendor draws them differently: the coach works out its own from the
heart rate the band sends (ADR-0055), so typed zone minutes would not match them.

## Decision

- **How hard it felt, 1 to 10 (session RPE), is asked on the web's cardio form** and must be
  picked to save there. Minutes times RPE is the session load (Foster 2001): it works with no
  device and compares across devices. "Done as planned", the HIIT rounds and typed or
  Telegram logs don't ask for it, so the API keeps it optional.
- **Optional, under "More from your watch or app":** distance in km, average and highest heart
  rate, and the local time it started. Pace is worked out from minutes and distance
  (`domain/cardio.pace`) and shown on the form and the saved screen. It is never stored.
- **Stored on the workout,** next to `activity`: `effort`, `distance_m`, `avg_hr`, `max_hr`,
  `started_at`. Each is empty unless given. The bounds live in `domain/cardio.py` and a check
  constraint: RPE 1-10, distance up to 300 km, heart rate 30-230, highest not below the
  average, and no distance for HIIT (rounds). The start is the last time the clock showed the
  time typed, so a run started at 23:40 and logged after midnight started yesterday.
- **A counted band workout carries the band's heart rate and start** onto the workout, but only
  when they pass the same bounds. An odd reading is dropped, so the walk is still counted. The
  band can't know how it felt, so effort stays empty there.
- **Not captured:** vendor scores, VO2 max per run, cadence, stride, splits, calories, steps
  and the route.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Effort plus optional distance, heart rate and start on the workout (chosen) | Short form; works with no device; compares across devices; same columns for band workouts | Typed heart rate can't give zone minutes |
| Copy every number the app shows | Nothing lost | A long form nobody fills in; vendor scores mean nothing across devices |
| Typed zone minutes | Feeds the zone 2 total directly | Each vendor's zones differ from the coach's (ADR-0055) |
| A separate cardio-details table | Workouts stay narrow | A join for five optional numbers, and one more thing to erase and export |

## Consequences

- The web's cardio form has a 1-10 row and an optional section, and the saved screen reads
  e.g. "effort 6/10 · 7.29 km · 5:54 /km · HR 139 avg, 160 max". A refused log says why.
- `domain/cardio.load` exists, but the weekly view doesn't show load yet. A load number needs
  a few weeks of logs before it means anything. Follow-ups: show it in the weekly review; an
  "effort" word in typed and Telegram logs ("run 43 min effort 6"); and the same details on a
  past day's log (`LogDay`).
- VO2 max fits better as an occasional measurement, like bodyweight, than as a field on each
  run. It is left for the Body page.
- Photo or screenshot prefill of these fields: `docs/specs/cardio-photo-prefill.md`.
