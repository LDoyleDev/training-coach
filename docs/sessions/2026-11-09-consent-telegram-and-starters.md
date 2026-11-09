# Session log: 8-9 Nov 2026 (1.20.0): consent, Telegram for members and the starters

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-07-joining-and-leaving.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.20.0 | Health questions on the device: #612 (drops `readiness_answers`, migration `b2d4f6a8c0e3`). Consent per category (ADR-0090): #617 records and withdrawing (`c3e5a7b9d1f4`), #618 a member's health data opens on consent, #620 the consent card and Account's list, #619 "private test" on joining, #636 and #640 proposals need a current yes. Starters (any-level S1): #626 rest places in the queue (`d5f7a9c1e3b6`), #628 the 2-, 3- and 4-day starters, #650 their gym swaps. Telegram for members (ADR-0089): #615 the sender gate, #614, #624, #632, #634 the bot uses the sender's data and consent, #639, #643, #644 connecting with a link and a code (`e7b9d1f3a5c8`), #647 user ids never reused (`f9c1e3a5b7d2`), #648 unlink, leave and erase drop the bot's memory of a person; #652 and #654 scheduled messages per person (joining step 9). #609 a member's erase drops their link. Docs: #613, #616, #621, #622, #588, #610. Members stay behind `TC_MULTI_USER`, off. |

Released with Liam's OK in chat (9 Nov, naming the release). Before the release PR was merged:
a manual backup (`training_coach-manual-20261109T200329Z.db`) and the same drill as 1.19.0, on
copies of that backup, with no network and no `.env`. All passed:

- Row data matched between the old image and the release image apart from what the release
  means to change: `readiness_answers` gone (Liam's one stored set of answers, deleted as
  ADR-0085 decided), the new empty tables (`consents`, `readiness_checks`, `telegram_links`,
  `telegram_claims`), `session_templates` (its new `rest_after`), `users` (rebuilt with
  AUTOINCREMENT and the Telegram columns; same row), three new hip hinge steps in `ladder_steps`
  and one more seed event. Plan tables stayed at 7 versions, 7 sessions and 124 items, every
  `user_id` 1.
- Integrity and `foreign_key_check` clean, no `seed.failed`, and the import's diff empty.
- Today, Progress, session times, Review, Plan, both body maps and Home answered 200 on both
  images, differing only by Today's new `rest_day`. The export differed only as intended.
- `alembic downgrade a9c3e5f7b1d2` (all five migrations) on another copy matched the backup's
  schema and rows, apart from `readiness_answers` (comes back empty) and the seed's additions,
  and the old image answered the same on it. The old image's seed logs `seed.failed` there: it
  won't shorten the hip hinge ladder the new seed lengthened. It still starts and serves; a
  rollback would need the three steps kept or a data migration to drop them.

Live at 21:20:20 CET by the deploy timer. The Pi's head is `f9c1e3a5b7d2`, `/healthz` says
1.20.0 with the bot on, the first start logged `seed.applied` (the three hip hinge steps) with no
`seed.failed`, and the live rows match the drill: integrity and foreign keys clean, plan tables at
7, 7 and 124, 270 ladder steps, `readiness_answers` gone. As the migration says, nothing was
copied into `readiness_checks`: Liam is asked the ten health questions again, on his device.

## Decisions and where they live

- **Consent opened per category, family and friends first, the lawyer before outside guests
  (Liam, 8 Nov):** ADR-0090.
- **The starters, all nine answers as proposed (Liam, 8 Nov):** `any-level-any-time.md`, S1
  Decided 1-9; rest places in the queue in ADR-0091.
- **The walk-through for new people: all 23 open decisions taken as recommended (Liam, 9 Nov):**
  ADR-0092 (in review).
- **A back exercise at the gym, so the lower back isn't amber there (Liam, 9 Nov):** the S1
  Decided list (in review).

## Open items and next steps

1. **The walk-through (#577 stage 5):** ADR-0092, its migration (`walkthrough_answers`,
   exercises per session, the start date), then the services, API and three web PRs. The
   migration makes the release after it one that changes live data, so it needs Liam's OK, a
   backup and a dry run on a copy.
2. **Waiting on Liam:** turning on `TC_MULTI_USER` (with the notice in the app and the DPIA's
   open items, multi-user-plan step 11); the clinician's and lawyer's lists in #556's body
   before anyone outside family and friends.
3. **Follow-ups:** a reload during Telegram connect loses the t.me link; the connect status keeps
   stale state after an error; after the owner's own erase his scheduled messages restart at the
   default times (all three from the helpers' notes, unchecked); the easy start (B6). The
   follow-ups from the 1.18.0 log still stand.
