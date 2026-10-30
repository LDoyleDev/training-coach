# Concrete kit steps for the vague ladder tops

Status: **Accepted (Liam, 25 Oct 2026; Option B for curl and triceps).** Built in
`plan.toml` by the follow-up to builder step 4. Nobody stood on any ladder's top step when it was
accepted (checked read-only on the Pi), so every rename below is safe. Builder step 4 (`program-builder.md`, ADR-0071) says "Heavier kettlebell" steps
become concrete steps with name, needs and cue, written in the seed, never generated.

Written for the owner's kit: 8 kg and 16 kg kettlebells (the 16 kg on its way), resistance
bands, stools as a bench, a pull-up bar (the plan already assumes it), maybe a weighted vest and
dumbbells later, and a gym on some days (the gym has everything, so nothing locks there).

## How ladder positions are stored, and what that allows

- Each person's place is `exercise_state.ladder_step_id`; every kept set records
  `set_logs.ladder_step_id`. Both point at a `ladder_steps` row, shared by everyone.
- The seed matches steps **by position**. It can **append** steps at the end, and **rename** a
  step in place only with a `renames = { "old" = "new" }` entry on the exercise when history or
  anyone's progress uses it. It refuses to shorten a ladder or move a name between positions
  (`seed._preflight`). Inserting a step in the middle would move everyone above it onto a
  different variation, so it needs a data migration and a backup first.
- So the safe shape for every ladder below is: **rename the vague top step in place to its
  first concrete step, then append the rest.** The renamed step keeps its id, its logged sets
  and anyone standing on it. Nobody's position moves.
- Each rename below keeps what the step already needed (the "Heavier kettlebell" steps already
  need `kettlebell:16`), so a person on one stays on a step that means the same load. The ones
  where the meaning would change are marked **Moves meaning** with what to check first.
- Before applying, check on the Pi (read-only, `tc-read`) who stands on each vague top step:
  `exercise_state` rows whose step is one of them. If nobody does, every option is safe.

## Two small code changes the proposal needs

1. **Cues on ladder steps.** `ladder_steps.cue` exists and the web shows it, but `plan.toml` has
   no way to write one. Proposed: an `[exercises.cues]` table keyed by step name, like `needs`;
   the seed writes it on every run (a cue is not history).
2. **Band strength in needs.** Steps can say `band` but not which one. Proposed: `band:light`,
   `band:medium`, `band:heavy`, met by that band or a stronger one. `dumbbells:12` and
   `backpack:10` already parse (this PR).

## Proposed steps

Needs use the catalogue's form. "+" marks appended steps; "rename" the step renamed in place.

### Kettlebell swing (`kb-swing`, Legs 3 x 15-20)

| Step | Needs | Cue |
| --- | --- | --- |
| Two-hand, 8 kg | kettlebell:8 | (as now) |
| One-arm, 8 kg | kettlebell:8 | (as now) |
| rename "Heavier kettlebell" -> **Two-hand, 16 kg** | kettlebell:16 | Same snap from the hips; the heavier bell floats lower, chest height is not the goal. |
| + **One-arm, 16 kg** | kettlebell:16 | Free hand out to the side; don't let the bell twist your shoulders. |
| + **Two-hand, 24 kg** | kettlebell:24 | Hike it deep between the legs before each rep. |

### Bulgarian split squat (`bulgarian-split-squat`, Legs and Arms 3 x 8-15 per side)

| Step | Needs | Cue |
| --- | --- | --- |
| rename "Heavier kettlebell" -> **Goblet hold, 16 kg** | kettlebell:16 | Bell at the chest, elbows in; lower straight down. |
| + **Goblet hold 16 kg, 3 s lowering** | kettlebell:16 | Three seconds down, drive up. |
| + **Suitcase hold, 16 kg + 8 kg** | kettlebell:8, kettlebell:16 | A bell in each hand, heavier on the side of the front leg; swap each set. |

### Single-leg Romanian deadlift (`single-leg-rdl`, Legs 3 x 10-15 per side)

| Step | Needs | Cue |
| --- | --- | --- |
| rename "Heavier kettlebell" -> **16 kg** | kettlebell:16 | Bell in the hand opposite the standing leg; hips square to the floor. |
| + **16 kg, pause at bottom** | kettlebell:16 | One second at the stretch, back flat. |

### One-arm kettlebell row (`kb-row`, Torso 3 x 10-18 per side; 10-20 until ADR-0078)

| Step | Needs | Cue |
| --- | --- | --- |
| rename "Heavier kettlebell" -> **16 kg** | kettlebell:16 | Hand and knee on the stools; check they're stable before loading. |
| + **16 kg, 3 s lowering** | kettlebell:16 | Pull to the hip, three seconds down. |
| + **16 kg, pause at top** | kettlebell:16 | Hold one second with the elbow past the ribs. |

The row's summary says "a bench or bed". It doesn't need `bench`: a bed or chair works too,
and household things need nothing (ADR-0064).

### Overhead triceps extension (`overhead-triceps-extension`, Arms 3 x 10-15)

8 kg to 16 kg doubles the load on a small muscle overhead; few people make that jump at 10-15.
**Chosen: Option B**, a harder 8 kg middle step, then 16 kg. It moves the meaning of the top
step, which was safe because nobody stood on it (Liam is on step 1 of 3).

| Step | Needs | Cue |
| --- | --- | --- |
| 8 kg, both hands | kettlebell:8 | (as now) |
| 8 kg, 3 s lowering | kettlebell:8 | (as now) |
| rename "Heavier kettlebell" -> **8 kg, 1.5 reps** | kettlebell:8 | Lower all the way, press halfway, lower again, then press to the top: that's one rep. |
| + **16 kg, both hands** | kettlebell:16 | Elbows in; lower only as far as your shoulders allow. |
| + **16 kg, 3 s lowering** | kettlebell:16 | Three seconds down behind the head, then press up in one. |

Not chosen, Option A: the top step becomes 16 kg straight away. Later, with dumbbells:
**Dumbbell 10-12 kg, both hands** (dumbbells:12) would be a natural middle step.

### Kettlebell curl (`kb-curl`, Torso 2 x 12-18, Arms 4 x 12-18; 12-20 until ADR-0078)

Same jump as the extension: 16 kg curls for 12-20 are far off for most people. **Chosen:
Option B**, safe for the same reason (Liam is on step 1 of 3).

| Step | Needs | Cue |
| --- | --- | --- |
| 8 kg | kettlebell:8 | (as now) |
| 8 kg, slow tempo | kettlebell:8 | (as now) |
| rename "Heavier kettlebell" -> **8 kg, 3 s lowering, pause at top** | kettlebell:8 | Squeeze for one second at the top, then take three seconds down. |
| + **16 kg, hammer grip** | kettlebell:16 | Hold the handle upright; elbows stay pinned to your sides. |
| + **16 kg, slow tempo** | kettlebell:16 | Two seconds up, three down; no swinging. |

Not chosen, Option A: the top step becomes 16 kg straight away. Later, with dumbbells:
**Dumbbells 10 kg** (dumbbells:10) and **12 kg** (dumbbells:12) suit curls better than a bell.

### Pull-up and chin-up (`pull-up` Torso 4 x 5-12, `chin-up` Arms 3 x 6-12)

| Step | Needs | Cue |
| --- | --- | --- |
| rename "Weighted backpack" -> **Vest or backpack, 5 kg** | pull-up bar, backpack:5 | Pack it tight and high so it doesn't swing. |
| + **Vest or backpack, 10 kg** | pull-up bar, backpack:10 | Same reps, chest to the bar. |
| + **Vest or backpack, 15 kg** | pull-up bar, backpack:15 | Add load only when every set of 5-12 is clean. |

"Weighted backpack" already needs a backpack, so the rename doesn't move meaning: anyone on it
stays on a loaded step (at 5 kg). The 8 kg kettlebell in a backpack is a fine 8 kg step if the
owner wants one: **Backpack with the 8 kg bell** (pull-up bar, backpack, kettlebell:8).

On 29 Oct 2026 Liam chose one step instead of the three, **Vest or backpack**, that takes load
from 5 kg in his own step (ADR-0072, Built 29 Oct). The 10 and 15 kg steps left the ladder by a
one-off migration he approved, as nothing used them; the 5 kg step was renamed in place.

### Dip (chairs) (`dip`, Torso 4 x 8-15)

| Step | Needs | Cue |
| --- | --- | --- |
| rename "Weighted backpack" -> **Feet off floor, 5 kg vest or backpack** | backpack:5 | Chairs back to back and braced against a wall; stop if they rock. |
| + **Feet off floor, 10 kg** | backpack:10 | Shoulders down, lower to upper arms level with the floor. |
| + **Dip bars, bodyweight, full range** | dip bars | Lean slightly forward; elbows back. |
| + **Dip bars, vest or backpack** (29 Oct 2026; takes load from 5 kg, ADR-0072) | dip bars, backpack:5 | Pack it tight and high so it doesn't swing; add weight only when every set of 8-15 is clean. |

The last one is a different set-up, not more load: listing "dip bars or two chairs" covers
chairs today, so it is only open once someone owns bars or trains at the gym (accepted as
written).

### Band face pull (`band-face-pull`, Cardio + core 2 x 12-20)

Needs change 2 above.

| Step | Needs | Cue |
| --- | --- | --- |
| Light band, Light band 2 s hold | band:light, pull-up bar | (as now) |
| rename "Heavier band" -> **Medium band** | band:medium, pull-up bar | Step back until taut; hands finish beside the ears. |
| + **Heavy band** | band:heavy, pull-up bar | Same height and pace; don't lean back to cheat it. |

The rename keeps meaning ("Heavier band" was any band).

### Zone 2 (`zone2`)

"Easy jog with weight vest or backpack" stays: a vest of any weight is fine for zone 2, and its
need (`backpack`) is already concrete. No change proposed.

### Not changed

- Goblet squat (retired, history only): left as is.
- Steps that hold "8 kg" low on the ladder (calf raise, tibialis, pistol, side plank hip dip,
  back extension, reverse fly) end at 8 kg on purpose; a 16 kg top for each can come later, by
  appending.

## What the 16 kg kettlebell unlocks

With the owner's kit listed (8 kg and 16 kg bells, bands, pull-up bar, stools as a bench), the
16 kg bell opens today: the six "Heavier kettlebell" steps, suitcase carry 16 kg and the farmer
carry (8 steps). With these ladders it opens 16 steps in seven ladders, each with a cue. A 24 kg bell adds the heaviest swing; a vest that loads to 15 kg opens 8 steps in pull-ups,
chin-ups and dips (a 5 kg one opens 3).

## Figures

Figures are per exercise (ADR-0063), so most new steps reuse theirs. These change the set-up,
and are drawn by step (ADR-0063's addendum, `frontend/src/figures/steps.ts`):

- Bulgarian split squat, **Suitcase hold, 16 kg + 8 kg**: bells at the sides, not the chest.
- Pull-up, chin-up and dip, the **vest or backpack** steps: a load prop on the torso.
- Dip, **Dip bars, bodyweight, full range**: bars in place of two chairs.
- Kettlebell curl, **16 kg, hammer grip**: the handle held upright.
- Overhead triceps extension, **8 kg, 1.5 reps**: the same pose, a different motion (a half
  rep in the middle); no figure: the set screen shows the step's cue.

## Decided (Liam, 25 Oct 2026)

1. The renames and appends above, as written.
2. Triceps extension and curl: Option B, an 8 kg middle step, then 16 kg.
3. The two code changes (step cues in the seed, band strength in needs) are built with the
   ladders.
4. Dip bars stay as the dip's last step.
