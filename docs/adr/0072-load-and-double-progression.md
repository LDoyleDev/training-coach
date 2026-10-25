# ADR-0072: Sets record their load; loaded exercises progress by reps, then weight

- Status: Proposed
- Date: 2026-10-25
- Deciders: Liam

## Context

A set has one value: reps, seconds or minutes. Progress is more reps within a range (ADR-0027)
and then a harder ladder step (ADR-0016). That fits bodyweight work and a single kettlebell, but
not dumbbells, a barbell, machines or a weighted vest, where the exercise stays the same and the
weight goes up in small steps. Liam will train at a gym some days and may get dumbbells and a
vest (25 Oct 2026). The builder settled the shape (`program-builder.md`, option D, Decided 6).

## Decision

- **Two ways to get harder.** An exercise is either a `ladder` (bodyweight or fixed kit, as
  today) or `load` (dumbbells, a barbell, a machine). A kettlebell at home stays a ladder step:
  8 to 16 kg is a different exercise, not a small step.
- **The top step of a ladder can take load.** "Weighted backpack" steps become "Added weight"
  steps that need a weighted vest or a backpack, and progress by load from there. So pull-ups,
  dips and push-ups keep their ladders and then add weight.
- **Each set records its load** (`set_logs.load_kg`, nullable; empty for bodyweight). For an
  added-weight step it is the weight added, not bodyweight plus.
- **It carries over.** The set screen starts at the load of the same set last time, at the same
  place, with − and + in the kit's increment. No typing.
- **Double progression.** Reps go up within the range as ADR-0027 says. When every set reaches
  the top of the range, the app suggests the next weight up, and the reps start again at the
  bottom; a missed target holds, as in ADR-0027. **The person decides:** the suggestion is a
  tap, never a change made for them.
- **Increments.** At home, the next weight you own (12 kg dumbbells after 10 kg, or the vest's
  own step). At the gym: barbell 2.5 kg, dumbbells 2 kg per hand, machines 5 kg. Each person
  can change theirs. Kilograms only (Decided 6).
- **Scope.** Targets and bests for a loaded exercise are kept per load as well as per block
  kind (ADR-0028), so a heavier weight starts from its own baseline, as a new ladder step does
  (ADR-0034). A strength block on a loaded exercise is 4-8 reps at a heavier load, instead of
  the next ladder step.
- **Logging by voice or text** stays reps-first: "rows 10 10 9 at 16" is parsed with the load as
  an optional part, and the confirm step shows it (ADR-0007).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Double progression with a suggested next weight (chosen) | The usual gym method; small steps; fits ADR-0027; the person decides | A new column and a second rule to explain |
| Fixed reps, weight up every session | Simple | Stalls quickly; ignores missed reps |
| Percentage of a tested one-rep max | Precise for strength blocks | Needs max tests; overkill for hypertrophy at home |
| Weight only in step names (today) | Nothing to build | No small steps; dumbbells and machines don't fit |

## Consequences

- Builder step 8: `set_logs.load_kg` (a migration), − and + on the set screen, the carry-over,
  the suggested next weight, bests and targets per load, and the parser's optional load. The
  Telegram summary and the weekly review show loads where they exist.
- The catalogue marks which exercises are `load`; the 29 gym exercises arrive with it.
- The body map is unchanged: it counts hard sets, not tonnage.
- Exports and the AI tools (ADR-0058) carry `load_kg`; `propose_log` accepts it.
