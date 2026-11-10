# Session log: 9-10 Nov 2026 (1.21.0): the walk-through

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-09-consent-telegram-and-starters.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.21.0 | The walk-through for new people (ADR-0092, #577 stage 5): #673 its schema (`walkthrough_answers`, `settings.session_exercises`, `settings.set_up_on`, `plan_state.starts_on`; migration `a1c3e5f7b9d2`), #674 exercises per session in the trim and a plan that starts on a day, #679 the one save that makes a member's plan, #685 its routes (`GET /api/walkthrough`, the preview, the save); on the web #676 the level, ladder walk and lock rules, #683 `/start` with consent, where you live and the health questions, #684 about you, what to avoid, where you train and the home kit, #686 the ladder walker and the days, minutes and exercises per session, #688 the starter and start day, #696 the plan screen, #697 Save and Done, #698 the ways in and the Plan hero from the plan; #694 one table of start-day cases for both copies, #700 a stub removed. #671 the 45° back extension at the gym, so the lower back is 4 (green) there on every starter. Fixes: #693, #701 and #702 (the two Telegram follow-ups from the 1.20.0 log), #705, #706. Docs: #666, #670. Members stay behind `TC_MULTI_USER`, off. |

Released with Liam's OK in chat (10 Nov, naming the release). Before the release PR was merged:
a manual backup (`training_coach-manual-20261110T183159Z.db`) and the same drill as 1.20.0, on
copies of that backup, with no network and no `.env`. All passed:

- Row data matched between the old image and the release image apart from what the release
  means to change: the new empty `walkthrough_answers`, and `settings` and `plan_state` with
  their new empty columns (same rows). Plan tables stayed at 7 versions, 7 sessions and 124
  items, every `user_id` 1. No ladder step or seed event changed.
- Integrity and `foreign_key_check` clean, no `seed.failed`, and the import's diff empty.
- Today, Progress, session times, Review, Plan, both body maps, Home and the import answered 200
  on both images; Home differs only by its new `walkthrough`, and `GET /api/walkthrough` answers
  200 on the release image (404 before). The export differed only by the new columns and table.
- `alembic downgrade f9c1e3a5b7d2` on another copy matched the backup's schema and rows exactly,
  and the old image started on it with no `seed.failed` and answered the same.

Live at 19:53:29 CET by the deploy timer. The Pi's head is `a1c3e5f7b9d2`, `/healthz` says
1.21.0 with the bot on, the first start logged `seed.unchanged` with no errors, and the live rows
match the drill: integrity and foreign keys clean, plan tables at 7, 7 and 124, 270 ladder steps,
`walkthrough_answers` empty and the new columns in place. The owner's plan is untouched; the
walk-through is his to try from Plan, and a member's waits on `TC_MULTI_USER`.

## Decisions and where they live

- **The walk-through: every open decision as recommended (Liam, 9 Nov):** ADR-0092 and its
  addenda.
- **The 45° back extension at the gym, the lower back's amber gone (Liam, 9 Nov):** the S1
  Decided list in `any-level-any-time.md`.
- **Adding and removing a session, 20 decisions (Liam, 10 Nov):** 18 as recommended, a cycle
  of any length among them (4). Two changed: a change to the cycle tells the person, as a plan
  notice (10), and the body map counts over the cycle's own length, its weekly bands stretched
  to it, instead of scaling to 7 days (15). ADR-0093 (in review, #707).

## Open items and next steps

1. **Adding and removing a session (#577 stage 4, the last part):** ADR-0093 first, then seven
   PRs. The second carries a migration (`session_templates.retired_on`), so the release after it
   changes live data: Liam's OK, a backup and a dry run on a copy.
2. **Waiting on Liam:** turning on `TC_MULTI_USER` (with the notice in the app and the DPIA's
   open items, multi-user-plan step 11); the clinician's and lawyer's lists in #556's body
   before anyone outside family and friends; the Dependabot PRs (#660's Gradle plugin needs its
   verification metadata trusted).
3. **Follow-ups:** after the owner's own erase his scheduled messages restart at the default
   times (from the 1.20.0 log, unchecked); the easy start (B6). The follow-ups from the 1.18.0
   log still stand.
