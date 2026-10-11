# ADR-0051: The HIIT timer works like Tabata Timer, with workouts saved in the browser

- Status: Accepted
- Date: 2026-10-11
- Deciders: Liam

## Context

The first HIIT timer (#201) asked for rounds, work and rest only. Liam uses the "Tabata Timer"
Android app (HIIT Apps) and wants the web timer to work the same way, so there is nothing new
to learn: prepare, work, rest, cycles, sets, rest between sets and cool down, plus a list of
saved workouts. The app saves only the rounds done (`kind: hiit`, a count), and nothing on the
server needs the timer's settings.

## Decision

- The timer follows the Tabata Timer model and defaults (prepare 10 s, 20 s on / 10 s off,
  8 cycles, 1 set, 60 s between sets, no cool down). A set's last cycle has no rest of its own;
  the rest between sets follows it, and there is none after the last set.
- Saved workouts and the voice-cue choice live in the browser's `localStorage`, read and written
  inside `try`/`catch`. Without storage the timer works the same and forgets on reload.
- The rounds saved are the work intervals completed across all sets. A work interval skipped
  with Skip does not count.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| localStorage (chosen) | No API, table or migration; works offline; one user on one phone | Not shared between devices; lost if site data is cleared |
| Server table of workouts | Same list on every device | An API, a migration and tests for settings nobody else reads |

## Consequences

- No backend change. A second device starts with the default Tabata workout.
- If workouts need to follow Liam across devices, move them to the server then; the stored
  shape (`id`, `name`, `settings`) is already clean to send.
