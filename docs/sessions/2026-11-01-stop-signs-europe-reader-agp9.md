# Session log: 1 Nov 2026 (1.15.0): stop signs checked for Europe, test-day warm-up, the reader on AGP 9

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-01-names-figures-deps.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.15.0 | #556 the stop signs reviewed against European sources: chest pain on its own with 112 straight away if severe or after 5 minutes of rest, faint/dizzy/heartbeat/sight, fever, pregnancy signs shown to everyone, "what's normal", one reminder line shared by the session page, Tests page and bot, clearance wording out of the readiness intro, the intended-purpose statement on Account; #555 a test day's warm-up line says 10 minutes, sessions keep 5; #484 the 3- and 4-day starters accepted without the six added sets (program-builder.md N); #557 the plan import ships with builder step 5; #551 the 1.14.0 log. No migrations. |
| Reader 0.0.8 (waits for Liam's `android-release` approval) | #554 AGP 9.3.3, Gradle 9.7.1, compileSdk 37, Kotlin 2.4.21 (built-in Kotlin), #470's library updates (closed as superseded), a permanent APK guard in `android.yml` (`android/app/expected-apk.txt`); #558 `VERSION` 0.0.8 (closes #553). |

Also on 1 Nov, with Liam's OK in chat: his glute bridge set to "Shoulders on the sofa (hip
thrust)" and plank to "Full plank" on the Pi, through `progress.set_level` (the same change and
`level_set` event as a tap on Plan). The Pi was unreachable from about 19:00 to 20:00 CET
(home network and Tailscale; the tunnel answered 530) while the app stayed up; it came back
by itself.

## Decisions and where they live

- **Liam's answers of 1 Nov:** test days keep a 10-minute warm-up (program-builder.md J.4,
  `TEST_DAY_WARM_UP_MINUTES`); the level questions as built (ADR-0075 addendum, confirmed);
  the starters without the extras (program-builder.md N); step 5 from about 4 Nov with the
  import (plans-per-person.md, open points); the reader's toolchain upgrade (#553).
- **The safety wording and its sources:** `any-level-research.md` Part 5 and the ADR-0085
  addendum of 1 Nov; the live text is `frontend/src/session/safety.ts`. PAR-Q+ can't be
  reproduced in the app; never call our questions PAR-Q or validated. The [0085] text for the
  on-device questions is written there for that build.
- **The reader's build:** `android/CLAUDE.md` (Gradle 9.7.1, built-in Kotlin, the APK guard);
  #554's body has the checksum review.

## Open items and next steps

1. **Waiting on Liam:**
   - **Cloudflare:** IP Geolocation and the WAF rule (`docs/runbooks/deploy.md`); Liam chose to
     have them made in his Chrome once he has signed in. Then #514 and #515.
   - **Reader 0.0.8:** approve `android-release`, install, Sync now, check the next day's
     background run.
   - **Dependabot alert 6 (minimatch 5.1.9, moderate):** reached only through openapi-typescript
     7.13's `@redocly/openapi-core` 1.x, which pins 5.1.9; the fix is minimatch 11, which 1.x
     doesn't take. Build-time only, no untrusted globs. Dismiss as tolerable or wait.
   - **Step 5 open points still open:** refuse or copy for members (refuse recommended),
     starters only in `plan.toml`, plan version notes.
   - **Before anyone else uses the app:** the clinician's and lawyer's lists in #556's body and
     Part 5.
   - The away versions (#539) and knees marks (#541, #546) to look over; the phone's adb check;
     the restore drill before step 5 (needs his OK).
2. **Step 5 from about 4 Nov:** the restore drill, a plan-critic review, the migration with the
   import, a backup and a dry run on a copy, released on its own.
3. **After builder step 5:** setup with placement and the on-device safety questions (ADR-0085,
   with Part 5's text), the starting starters, the easy start.
4. **Follow-ups:** the Tests page could say "about 10 minutes" for the warm-up (#555 only
   changed the bot); `api/settings.py` and `db/models.py` comments still say "where it's
   safe"; the APK guard and the release job take the highest `build-tools` folder, which could
   be a preview.
