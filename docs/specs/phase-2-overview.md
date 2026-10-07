# Phase 2: the overview (draft)

Status: **draft, not agreed.** Scope comes from the product spec; the steps and acceptance
criteria below are a proposal to react to. Settle the open decisions with Liam, then turn each
step into an issue in milestone **Phase 2 - Overview** and remove "draft" from this file.
Target version: 1.0.0 (phase 2 complete and in daily use, ADR-0005).

Goal: Liam can see whether the training is working (baselines, retests, measurements, weekly
volume and bests) on his phone, and share a read-only view with others. Phase 1 must be done
and one real week logged first.

## Open decisions (before any issue is opened)

Options and recommendations for D2, D4 and D6: `phase-2-decisions.md`. A wider proposal (web app
without Telegram, a standalone app, wearable data): `platform-and-health-data-proposal.md`.

| # | Decision | Why it matters |
| --- | --- | --- |
| D1 | Dashboard visual design and screen list (`dashboard-design.md` says it is agreed first) | Every web step depends on it |
| D2 | Monthly strength/hypertrophy blocks (#26): block length, how targets and ladder steps change, how progression counts across blocks | Changes the target and progression rules from ADR-0016; needs an ADR |
| D3 | Where progress photos are stored, and whether they are encrypted at rest | Most sensitive data in the app; SD card and backups |
| D4 | Retest cadence: fixed every N weeks, or prompted at the end of a block | Drives the reminder logic |
| D5 | Which habits to track (product spec: morning light, sleep, protein) and how (one tap each, or a daily check-in) | Data model and message design |
| D6 | Weekly review day and time (product spec: Sunday) | Scheduling |

## Proposed steps (draft)

Order: data first, then Telegram features, then the dashboard that shows them.

### 2-A Baseline tests and retests
- Model for test definitions (from the product spec list) and results with date and conditions.
- `/baseline` walks through day 1 and day 2 tests in Telegram, one test at a time, with the
  same confirm-before-save rule as workout logs (ADR-0007).
- Retest reminder per D4; results comparable test by test.

### 2-B Body measurements and progress photos
- Measurements (bodyweight, waist, chest, upper arm, thigh, resting heart rate) logged by text.
- Photos stored per D3; never in logs, never in share views (ADR-0012), excluded from any
  public endpoint (ADR-0019).

### 2-C Weekly review message
- Scheduled per D6: sessions done vs planned, hard sets per muscle group vs Galpin's 10-20,
  personal bests, exercises ready to progress.

### 2-D Habit check-offs
- Per D5. One message or buttons; streaks shown in the weekly review.

### 2-E Strength and hypertrophy blocks (#26)
- Per D2 and a new ADR. Morning message names the current block and prompts the warm-up.

### 2-F Dashboard login and share links
- Owner sign-in and read-only share links exactly as ADR-0012 (Telegram HMAC, hashed expiring
  tokens, `/share` and `/unshare`). Every route declares owner-only or share-visible; tests
  enforce it. Cloudflare WAF and rate limit on `/api/auth/*`.

### 2-G Dashboard screens
- Built to the agreed design (D1): Today, Plan with live position and ladder progress,
  Progress charts, Baseline vs retests, Measurements, Share view. Works as a Telegram Mini App.

### 2-H Guided session mode
- One exercise at a time with a rest timer, in Telegram or the Mini App.

## Definition of done (phase)
- All steps merged; release 1.0.0; in daily use for at least two weeks.
- Restore drill repeated with photos and measurements in the backup.
