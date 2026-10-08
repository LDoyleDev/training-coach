# ADR-0031: Resistance sessions are done in fixed pairs, listed set by set

- Status: Accepted
- Date: 2026-10-08
- Deciders: Liam (#97)

## Context

Sessions listed each exercise once, with all its sets ("Pull-up: 8 / 8 / 7"). Liam trains in
alternating pairs and wanted the list in the order it's done, so he can work down it, and the
same list should be easy to log from. Pairing exercises that don't compete for the same muscles
(opposing muscles, or legs with something light) also shortens a 60-minute session: one
exercise rests while the other works.

## Decision

- Pairs are fixed in `plan.toml`: `pair = N` on two neighbouring items. The seed refuses a
  pair number that isn't on exactly two neighbours, and stores the number on `template_items`.
- The plan's order (power -> strength -> hypertrophy -> small muscles) applies to each pair's
  first exercise. The second can be a small muscle that fills the bigger lift's rest (calf
  raise with KB swing), so some small-muscle work moves earlier than that order would put it.
- The order is pure logic (`domain/work_order.py`): a pair alternates A1, B1, A2, B2, ...; the
  exercise with more sets finishes alone; unpaired items are done straight through.
- `/today`, the morning message and Start show one numbered line per set in that order, with
  that set's target and a gap between pairs. Start puts the cues above the list, so the list
  is the last thing in the message.
- The parser drops the numbering, so the list can be copied, the numbers changed to what was
  done, and sent back as the log.

First pairs: Legs: jump squat + tibialis raise, KB swing + calf raise, Bulgarian split squat +
hamstring curl, pistol squat + single-leg RDL. Torso: pull-up + dip, KB row + push-up, pike
push-up + reverse fly, neck flexion + neck extension. Arms: chin-up + diamond push-up, KB curl
+ lateral raise, calf raise + hanging raise, neck lateral + neck extension; dead hang alone.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Fixed pairs in plan.toml (chosen) | Predictable; changing a pair is a reviewed edit like the rest of the plan | Pairs are maintained by hand |
| Automatic pairing by muscle group | Nothing to maintain | Odd pairs in an all-legs session; less control |
| Power exercises alone, the rest paired | Best for power output | Longer sessions; Liam chose pairs throughout |

## Consequences

- Messages are longer (one line per set), but they're the list to train and log from.
- A plan change that moves items must keep pairs on neighbours, or the seed refuses it.
- The dashboard (D1) will get the same order from the API, computed by the same domain function.
