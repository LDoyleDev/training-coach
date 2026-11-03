# Session log: 1 Nov 2026 (1.13.0): fifteen ladders go lower, the Squat comes back

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-01-away-preferences-entry-exercises.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.13.0 (live 1 Nov, 13:31) | #534 alone, as Liam chose: easier steps below the bottom of fifteen ladders (push-up from a wall, side plank, row, pull-up, calf raise, carry, curl, lateral raise, split squat, Copenhagen, back extension, zone 2, and a seated hold for the three neck ladders) and the retired `goblet-squat` back as the Squat with eight sit-to-stand steps; migration `5ebed72122f7` (ADR-0083, "One migration, one release"); #542 the 1.12.0 log. |

## Decisions and where they live

- **How it was released:** ADR-0083's addendum "the migration as built (#508)". Liam's OK on
  1 Nov after the read-only Pi check (all 16 ladders as expected) and two dry runs on fresh
  backup copies, before and after 1.12.0 (58 steps kept their ids, every set, level and event
  unchanged, 36 new steps unused, downgrade round trip clean). Copies deleted.
- **On the Pi after the deploy** (read-only): 94 steps on the sixteen exercises, 189 set logs
  and 16 levels on them, as before; the Squat is `Squat`, not retired; `seed.applied` updated
  38, as in the dry run.

## Open items and next steps

1. **Step numbers moved:** "Strict pull-up 2/4" now reads 4/6; levels and history are where
   they were. `start` names the same steps, so nobody's starting point changed.
2. **#545, in progress:** knees marks on the new deep steps, names that no longer fit their
   bottom steps, and figures for the new steps and the door-frame exercises.
3. **Backups kept on the Pi for 35 days:** `training_coach-manual-20261101T062611Z.db` and
   `training_coach-manual-20261101T084239Z.db` (taken for the dry runs).
4. Everything else is in the 1.12.0 log's open items.
