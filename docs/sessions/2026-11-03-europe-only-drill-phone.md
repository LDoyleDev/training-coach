# Session log: 2-3 Nov 2026 (1.16.0): the restore drill, the phone check, the EU and EEA only

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-01-stop-signs-europe-reader-agp9.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.16.0 | #514 the bot and a connected AI pause 30 days after the person's last signed-in visit from the EU or EEA (ADR-0085 layer 4), the band reader's import exempt from the region check; migration `f3a9c1d7e5b2` (`users.country`, `users.last_seen_in_europe`, everyone marked seen at the migration), re-chained after `5ebed72122f7` before merging; #515 the country of residence on Account, from the list, "Somewhere else" refused (layer 3 until sign-up); #566 the restore drill; #567 the band runbook's phone check. |
| Reader 0.0.8 | Published 2 Nov (approved by Liam) and installed on the phone. |

Released with Liam's OK in chat (3 Nov): a Pi check, a dry run of the migration on a copy of the
live file (40 tables, no count changed, `foreign_key_check` clean, integrity ok), and a manual
backup (`training_coach-manual-20261103T185010Z.db`) before the release PR was merged. Live
at 20:21 CET; the Pi's head is `f3a9c1d7e5b2`. The release PR needed a close and reopen to
start its checks.

Also, with Liam's OK:

- **The restore drill before step 5 passed on the Pi, 2 Nov** (`backup-restore.md`, Rehearsal).
- **Cloudflare, 2-3 Nov:** the WAF rule "Coach: EU and EEA only (ADR-0085)" is live, scoped to
  the app's host, with the band reader's import added on 3 Nov; IP Geolocation was already on
  (`deploy.md`, "The EU and EEA only"). Checked from Germany: `/healthz` and `/signin` 200.
- **Dependabot alert 6 (minimatch 5.1.9)** dismissed 2 Nov as not used: 5.1.9 lacks the
  advisory's code, and it is reached only at build time through openapi-typescript's
  `@redocly/openapi-core` 1.x. Revisit when openapi-typescript moves to openapi-core 2.x.

## Decisions and where they live

- **The phone (2 Nov):** the reader closing was MIUI's `LockScreenClean` (lock it in recents);
  Autostart off meant no background job after a restart; heart rate reaches Health Connect only
  when Mi Fitness is opened. All in `band-import.md`; Liam changed the settings.
- **The Europe gate:** ADR-0085; the rule's text and state, `deploy.md`.

## Open items and next steps

1. **Waiting on Liam:**
   - **Step 5 open points:** refuse or copy for members (refuse recommended), starters only in
     `plan.toml`, plan version notes.
   - **Before anyone else uses the app:** the clinician's and lawyer's lists in #556's body.
   - The away versions (#539) and knees marks (#541, #546) to look over.
   - Optional: an automation that opens Mi Fitness daily, so heart rate isn't held back.
2. **Step 5 from about 4 Nov:** a plan-critic review, the migration with the import, a backup
   and a dry run on a copy, released on its own.
3. **After builder step 5:** setup with placement, the country question and the on-device
   safety questions (ADR-0085), the starting starters, the easy start.
4. **Follow-ups:** the Tests page could say "about 10 minutes" for the warm-up;
   `api/settings.py` and `db/models.py` comments still say "where it's safe"; the APK guard and
   the release job take the highest `build-tools` folder, which could be a preview.
