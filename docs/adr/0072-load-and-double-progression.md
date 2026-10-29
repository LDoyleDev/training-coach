# ADR-0072: Sets record their load; loaded exercises progress by reps, then weight

- Status: Accepted
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

- **The progress chart shows each weight, and each ladder step, as its own period** (Liam, 25
  Oct 2026). The line breaks at a change; periods alternate between plain and a faint neutral
  tint, each labelled with its weight or step and an arrow ("16 kg ↑", "12 kg ↓", "Step 3 ↑"),
  so the drop in reps after a step up reads as the method working, not a decline. A step down
  is marked too. Text carries the meaning, never colour alone, and the chart's description says
  it in words ("moved to 16 kg; reps 12 → 8"). This applies to ladder steps straight away.
  When loads arrive, a thin strip under the chart, on the same dates, shows the kg (or the step
  number) as a staircase.
- **One axis, never two.** Liam asked about a second scale on the right; it's left out because
  two scales line up arbitrarily and suggest a link the data doesn't show, and a second set of
  labels costs a phone chart about a tenth of its width (Datawrapper, the ONS and Stephen Few
  advise against dual axes; the strip is the honest version). A colour per weight runs out of
  hues and fails colour-blind readers, so the tints alternate.
- **No converted "estimated strength" line for now.** One-rep-max formulas hold up to about
  10-12 reps and have no validation for bodyweight work (Reynolds 2006), and converting ladder
  steps would invent progress (ADR-0034). It may come later as an optional, labelled view for
  loaded exercises only.

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

## Built (26 Oct 2026)

Decided while building, within this ADR:

- **A step takes load, not an exercise.** `plan.toml` names the steps that take load and what
  carries the weight (`[exercises.loads]`: `barbell`, `dumbbells` or `machine`, a cable
  counting as a machine), so a gym exercise is a one-step ladder that takes load. The kit gives
  the increment (2.5, 2 and 5 kg). The vest and backpack steps stay ladder steps with their
  weight in the name (`kit-ladder-proposal.md`, accepted after this ADR); a loaded "Added
  weight" step past them is a plan change for later.
- **Where a set starts:** the same set's weight in the last session at that step and block
  kind with a weight; a set not done then starts at the nearest set before it. With no
  history, the kit's first weight (the 20 kg bar, 8 kg dumbbells, a 20 kg stack), a starting
  point for − and +, never a suggestion. Each person's own increments, and the next weight
  owned at home, wait for places (builder step 9): until then nothing tells home from gym.
- `set_logs.load_kg` is more than 0 and at most 500 kg; a guided set sends it only for a
  loaded step, and it is kept with the set's progress, saved on its rows, and comes back with
  /undo of a replaced day.
- **Typed and spoken logs:** one weight per line, for the line's sets: "rows 10 10 9 at 16",
  "@ 22.5", or "60 kg" before or after the reps; a decimal comma is fine. A weight on a step
  that doesn't take load is a problem shown at confirm ("Dip isn't done with a weight"), never
  dropped silently; two weights on one line ask for a line each. The confirm step shows "10 /
  10 / 9 at 16 kg"; a set given no weight shows a dash in its place ("8 / 8 / 6 at 16 / 16 / –
  kg") and is saved without one: the person decides. The AI's `propose_log` and the summaries follow in their own PR.
- **A session's weight is its heaviest set's.** Targets come from the sessions at the weight
  last used, so a heavier weight starts from its own first session; bests after a save count
  only sessions at the same weight. The suggestion is the next weight by the kit's increment
  once the last session did every planned set at that one weight and every set reached the top
  of the range (one session, as option D says; a ladder's Move up needs two). A pyramid, one
  heavy set and the rest lighter, suggests nothing: it is no session at the heavy weight. It comes with targets at the bottom
  of the range and changes nothing until the person takes it on the set screen. A loaded step
  is never "ready to move up" or "top of the ladder": it gets harder by weight.
- **Taking it is the tap alone.** Use or Stay on the set screen is kept in that browser for
  the day's session, so a reload keeps it; reaching the suggested weight with + is not taking
  it. Use or Stay restarts only the sets never confirmed.
- **Strength blocks:** a loaded step stays on its step with the 4-8 prescription and no tempo
  cue; its weights and targets come from strength-block sessions, so the first strength block
  starts at the kit's first weight and the person sets theirs. The weekly review's bests still
  count every weight.
- **Bests name their weight** (28 Oct 2026). After a save they name the session's weight,
  which they were counted at: "New best on Hammer curl at 12 kg: ..." in Telegram, "new best 12
  in one set at 12 kg" on the saved screen. The weekly review, which counts every weight, names
  that of the session that set the best set: "Hammer curl (Dumbbells, at 12 kg)".
- **The chart by weight:** once any session in the six weeks has a weight, the periods follow
  the session's heaviest set ("22 kg ↑"; a session without one is "No weight"), and a strip
  under the chart draws the weight as a staircase on the same dates, labelled with its lowest
  and highest kg and described in words. An exercise without weights keeps its step periods
  and has no strip. The strip breaks at a session without a weight, as the chart starts a
  "No weight" period there.
- **The summaries** (28 Oct 2026). Today's day log and the AI's read tools (`get_summary`,
  `get_exercise`, "Copy for my AI", guide version 4) write a line's weights as the confirm step
  does: "10 / 10 / 9 at 16 kg", "at 16 / 16 / 18 kg" when the sets differ, a dash for a set
  without one. The export already lists `load_kg` with every set.
- **The gym catalogue:** 23 exercises from Decided 5 that the home plan lacks, each one step
  that takes load (the 45° back extension: bodyweight, then holding a plate), with the
  research file's weights, a summary and typed-log aliases. The split squat, Copenhagen plank,
  tibialis raise, carries, neck work and hanging raises stay the home exercises' own ladders.
  They name no kit (a gym has everything) and are in no session until the gym versions
  (builder step 9); until then they are logged by text or voice, and an exercise in no
  session shows on Progress once it has been logged. Their figures (ADR-0063) came in 1.7.0,
  with step 9's gym versions.
- **The AI's proposals** (28 Oct 2026). A strength line in `propose_log` (ADR-0058) may carry
  `kg`: one weight for all its sets or one per set. It is written into the log text as a typed
  weight is ("rows 10 10 at 16", a line per run of sets at one weight), so the rule parser
  checks it the same way: only on a step that takes load, more than 0 and at most 500 kg, to
  0.01 kg. The card and the Telegram message show it ("10 / 10 / 9 at 16 kg"), and Save writes
  it to `load_kg`.

## Confirmed (29 Oct 2026)

Liam confirmed the choices made while building own increments and the next weight owned at
home (below): weight steps are set on Account only, 0.25 to 20 kg in quarters; − and + step
through the weights owned at home, and a first set starts at the lightest. He changed one: the
vest and backpack also count as weight owned at home, so the pull-up and chin-up "Vest or
backpack" steps become one step that takes load from 5 kg, and dips gain a loaded step after
dip bars. That is built in its own PR, with an addendum here.

## Built (own increments, 28 Oct 2026)

Decided while building, within this ADR:

- **Where:** "Weight steps" on Account, under My equipment: one step for each kit (barbell,
  dumbbells per hand, machine or cable), shown with its default. − and + on the set screen move
  by it, and the suggested next weight adds it, at home and at the gym.
- **Stored per person** on `settings` (`barbell_increment_kg`, `dumbbells_increment_kg`,
  `machine_increment_kg`); empty keeps the default, and a step set back to the default is kept
  as empty, so a later change to a default reaches them. A step is 0.25 to 20 kg, in quarters
  of a kilo. `PATCH /api/settings` takes `increments`, only the kits sent change.

## Built (the next weight owned at home, 28 Oct 2026)

Decided while building, within this ADR:

- **Which kit:** only dumbbells are both a loaded kit and something a person lists in My
  equipment; a barbell or a machine is the gym's, and the kettlebell, vest and backpack steps
  are ladder steps (Built, above). A home day is one whose version is the home one
  (`workouts.place`, ADR-0071), so a session without a gym version counts as home wherever it
  is done.
- **The weights owned** are each fixed pair, plus an adjustable set's weights from its lightest
  in the person's own dumbbell step, and its heaviest. With no kit listed yet, or a kit with no
  dumbbells in it, nothing is known, so the increment rule stands, as nothing locks then
  (ADR-0071).
- **At home, − and + step through the weights owned** ("At home, the next weight you own" is
  the increment there), and a first set with no history starts at the lightest one owned. At
  the gym, − and + and the next weight follow the increment.
- **Owning none heavier:** nothing is suggested, and the set screen says "Top for your kit: 18
  kg dumbbells would open the next weight", the last weight plus the person's step, as "top
  for your kit" names what opens the next ladder step.
- The home versions in `plan.toml` have no loaded step yet, so on the set screen this waits
  for a home version with one (editing the plan, builder step 6).

## Built (vest and backpack, 29 Oct 2026)

Decided while building, within this ADR, from Liam's answers of 29 Oct (Confirmed, above):

- **A vest or backpack carries load.** `[exercises.loads]` takes `backpack`: a weighted vest
  or a backpack, adjustable or packed with books, bottles or plates. A set's kg is the weight
  added, as for any added-weight step. A first set with no history starts at 5 kg.
- **Its own weight step** on Account, "Vest or backpack", 1 kg by default
  (`settings.backpack_increment_kg`, stored like the others: empty keeps the default).
- **The weights owned at home** run from 5 kg up to what the listed vest or backpack holds (its
  "up to" kg) in the person's step, with that top weight itself: a 10 kg vest in 2.5 kg steps
  is 5, 7.5 and 10 kg. A vest listed under 5 kg is its own weight only. At the gym, and with no
  kit listed yet, the increment rule stands. Owning none heavier is "Top for your kit: weighted
  vest or backpack, up to 11 kg would open the next weight". The set screen calls it "Added
  weight, kg". An exact weight in between ("dips 8 8 at 7.3") is typed or spoken, as for any
  loaded step.
- **Dips:** every chair step stays, and "Dip bars, vest or backpack" is appended after "Dip
  bars, bodyweight, full range" (needs dip bars and a vest or backpack of 5 kg), so nobody's
  step moves. Its figure is the dip-bars one with the pack on the back. It is the first loaded
  step in a home version, so the weights owned now show at home. Appending a step adds no plan
  version, as with the kit ladders (25 Oct).
- **Pull-up and chin-up: one step.** Their three "Vest or backpack, 5 / 10 / 15 kg" steps
  couldn't become one without a data change: the seed matches steps by position, refuses a
  shorter ladder (`seed._preflight`), and a rename keeps one position. Liam approved a one-off
  migration (29 Oct; `b7e1c3d5f9a2`), checked first on the Pi, read-only: nothing used the 10
  or 15 kg steps. It finds them by exercise and name, stops before any write if a logged set,
  someone's level, a guided session in progress or a workout kept for /undo uses one, and
  deletes them; sets at the 5 kg step without a weight get 5 kg (there were none). The seed
  then renames "Vest or backpack, 5 kg" in place to "Vest or backpack", which takes load
  carried by the vest (needs the bar and a 5 kg vest or backpack), so anyone on it stays on
  it. The figure is the 5 kg one's. A downgrade puts the two steps back at the top, without
  what was logged since.
