# Session log: 24 Oct 2026 (v0.38.0): our own band reader, and a security review

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-24-evals-dst.md`.

## Shipped

| Release | PRs |
| --- | --- |
| v0.38.0 (24 Oct, released with this log) | #316 the band reader spike: steps and heart rate from Health Connect (ADR-0070); #322 reader and CI hardening; #321 the person picks zone 2 or moderate on an AI's cardio proposal; #320 `propose_log` hardening; #324 limits on what one stolen band secret can do (migration: `imported_workouts.sustained_hr`); #317 and #323 the read-only Pi helper's limits and the deploy resume checks; #318 auto-deploy survives cut-offs and full disks, and prunes old images; docs #315, this log |
| Reader android-v0.0.1, android-v0.0.2 (24 Oct, pre-releases) | 0.0.1 is the spike; 0.0.2 has the built-in address, password field and the signing outside Gradle. Install 0.0.2 |

## Decisions and where they live

- **Band bridge: our own reader.** HC Webhook 1.9.31 still ran out of Health Connect's quota on
  the phone, so Liam chose to build it: ADR-0070 (Proposed until a three-day trial),
  `docs/specs/android-reader.md`, `android/CLAUDE.md`. Signing key: ADR-0070, Decision.
- **Cardio from an AI: the person picks the kind.** "The app can make observations and
  suggestions, but then the user has to decide." Minutes are the moving or active time.
  ADR-0067 addendum (24 Oct); the suggestion comes from the person's heart-rate zones.
- **Max heart rate from the band** rises only on a held reading, at most 20 bpm over the
  estimate, and Telegram says when it moves: ADR-0055 addendum (24 Oct).
- **Deploys:** an interrupted deploy is finished or rolled back with the same checks as a new
  one; old images of this app are pruned; a re-made release tag is refused: ADR-0030 addendum.

## Security review (24 Oct)

Five read-only or local checks: GitHub and CI, the Android app and phone, the desktop, the
Pi-side changes (locally, never the live Pi), and a gentle outside probe of the live coach. No
leaked secret and no active compromise was found. Fixed in this release: #322, #323, #324.
Repo settings changed with Liam's OK: immutable releases on; a tag ruleset (`v*`,
`android-v*`: no move, no delete, admin bypass). Not possible on this account: restricting tag
creation (would block release-please), secret-scanning extras.

Accepted for now (recorded in ADR-0070 and the threat model): a compromised Gradle dependency
could still change the unsigned APK before it is signed; `@claude` on a PR opened from a fork
isn't refused on issue comments.

## State at the wrap

- **Pi.** v0.37.2 live; v0.38.0 deploys after this log merges, with one migration
  (`sustained_hr`). `~/bin/tc-read` is still the 24 Oct morning copy: the new one (#317, #323)
  needs Liam's OK to install.
- **Band data.** None since 2026-10-19. Next: the reader trial.
- **Signing key backup** re-encrypted to the Training Coach backup key and copied to the Pi.

## Open items and next steps

1. **Phone:** approve and install reader 0.0.2 (check the certificate digest in
   `android/SIGNING_CERT_SHA256`), turn HC Webhook's permissions off and uninstall it, make a
   new secret, then three days of: open Mi Fitness, Sync now. Report the result line.
2. **Liam to check:** that "Training Coach backup key" really is in the password manager
   (`docs/runbooks/backup-restore.md` says so; unverified). If not, add it from
   `%USERPROFILE%\.age\training-coach-backups.txt` and correct the runbook.
3. **Liam's settings:** Cloudflare "Always Use HTTPS" (plain http serves the app today); disable
   the unused local admin account `User` on the desktop if it isn't needed; BitLocker status.
4. **Follow-ups:** Gradle dependency verification (closes the accepted APK gap); `/healthz`
   shows the version and bot state publicly; Dependabot PRs #325 to #331 to review (#325 is
   Node 22 to 25, a major, and should be closed).
5. **Builder stages, coverage gaps, figures:** as in the earlier logs.
