# Session log: 25 Oct 2026 (v0.38.1): reader diagnostics and dependency updates

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-24-reader-security.md`.

## Shipped

| Release | PRs |
| --- | --- |
| v0.38.1 (released with this log) | #333 reader 0.0.3 (below); dependency updates #326 (npm minor/patch), #327 (Python minor/patch), #329 (CodeQL), #330 (claude-code-action), #331 (setup-uv); this log |
| Reader android-v0.0.3 (pre-release, waits for Liam's approval in the `android-release` environment) | Keeps the screen awake during a sync; when Health Connect refuses a read, the result line names that read and how many reads the sync had made; reads in pages of 5,000; the first sync reads 24 hours, not 7 days (`docs/specs/android-reader.md`) |

Closed without merging: #325 (Node 22 to 25 is a major; Node 22 is pinned by ADR-0004) and #328
(the Gradle group needs `androidx.core` 1.19, which needs compileSdk 37; that upgrade is a
deliberate follow-up, below).

## What happened with the band

Reader 0.0.2 synced only in the foreground (Health Connect's rule without the background
permission) and then hit the same "request quota has been exceeded" refusal that HC Webhook
did. 0.0.3 exists to tell us which read runs out and after how many, on a fresh quota.

## State at the wrap

- **Pi.** v0.38.0 live and healthy; v0.38.1 deploys after the release PR merges. The new
  `~/bin/tc-read` (#317, #323) is installed with Liam's OK and checked (status, a SELECT, a
  refused UPDATE, the logs no-match message); the old copy is `~/bin/tc-read.bak-20261024b`.
- **Band data.** None since 2026-10-19.

## Open items and next steps

1. **Phone, tomorrow morning:** approve the android-v0.0.3 release run, update in Obtainium,
   open Mi Fitness, then one Sync now in the reader with the screen on. Report the result line.
   If it fails after a few reads on a fresh quota, Health Connect readers are ruled out and
   ADR-0070 moves to Gadgetbridge; if it works, the three-day trial continues.
2. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
3. **Follow-ups:** Gradle dependency verification; `/healthz` shows the version and bot state
   publicly; a Dependabot ignore rule for Node major tags; AGP, Kotlin 2.4 and `androidx.core`
   1.19 together with compileSdk 37.
