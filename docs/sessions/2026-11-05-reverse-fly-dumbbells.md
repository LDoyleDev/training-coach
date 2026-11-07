# Session log: 4-5 Nov 2026 (1.17.0): the reverse fly on dumbbells

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-03-europe-only-drill-phone.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.17.0 | #571 the reverse fly goes from water bottles to "Chest on bench/bed, dumbbells", a step that takes load: the 8 kg step renamed in place, "Chest-supported, 3 s lowering" removed by migration `c8d2e4f6a1b3`, and an away exercise's step that takes load must name its kit; #568 the 1.16.0 wrap. |

Released with Liam's OK in chat (5 Nov): a Pi check that nothing used either step, a dry run of
the migration on a copy of the live file, repeated on the day (40 tables, `ladder_steps` 268 to
267, `foreign_key_check` clean, integrity ok), and a manual backup
(`training_coach-manual-20261105T185109Z.db`) before the release PR was merged. Live at 20:10
CET; the Pi's head is `c8d2e4f6a1b3`, and the ladder is 46 water bottles, 47 dumbbells. The
release PR needed a close and reopen to start its checks.

Checked on a copy, with Liam's kit (adjustable dumbbells, 2-15 kg): at home the dumbbell step
starts at 2 kg and steps through 2, 4, 6, 8, 10, 12, 14 and 15 kg. Liam stays on water bottles
until he moves up, and away stays on water bottles.

Also: the merged worktrees and old local branches were cleared, keeping `draft/traps-rear-delts`.

## Decisions and where they live

- **The reverse fly (Liam, 4 Nov):** dumbbells of varying weight, the 3 s lowering step gone:
  ADR-0072, Built (the reverse fly on dumbbells).

## Open items and next steps

1. **Waiting on Liam:**
   - **Step 5 open points:** refuse or copy for members (refuse recommended), starters only in
     `plan.toml`, plan version notes.
   - **Before anyone else uses the app:** the clinician's and lawyer's lists in #556's body.
   - The away versions (#539) and knees marks (#541, #546) to look over.
   - Optional: an automation that opens Mi Fitness daily, so heart rate isn't held back.
   - `draft/traps-rear-delts` (local only, superseded by the face pulls): keep or delete. The
     remote branches `feat/507-entry-figures-a` and `-b` are his to delete, if he wants.
2. **Step 5, on Liam's answers:** a plan-critic review, the migration with the import, a backup
   and a dry run on a copy, released on its own.
3. **After builder step 5:** setup with placement, the country question and the on-device
   safety questions (ADR-0085), the starting starters, the easy start.
4. **Follow-ups:** the Tests page could say "about 10 minutes" for the warm-up;
   `api/settings.py` and `db/models.py` comments still say "where it's safe"; the APK guard and
   the release job take the highest `build-tools` folder, which could be a preview.
