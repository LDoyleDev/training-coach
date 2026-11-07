# Session log: 7 Nov 2026 (1.19.0): editing, joining and leaving

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-07-lengths-shorter-than-the-session.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.19.0 | Roadmap #577 stages 2-4: #582 change notices (migration `d7a3f9c1e5b8`); #583 edit your own plan; #584 the live body map; #592 picker details; #593 the hour and push/pull warnings; #594 a muscle names what would add to it. Joining (`multi-user-plan.md`), all behind `TC_MULTI_USER`, off: #595 roles (`e2f4a6c8b0d1`); #596 and #597 invites and `/join` (`f6a8c0e2d4b7`); #598 the Groq cap; #599 erase keeps the role; #600 leaving and the left list (ADR-0088); #601 off means off; #602 and #603 leave and remove; #604 the wind-down (`a9c3e5f7b1d2`); #605 and #607 the admin recovery link; #606 the closing page; #608 members training-only. |

Released with Liam's OK in chat (7 Nov). Before the release PR was merged: a manual backup
(`training_coach-manual-20261107T223454Z.db`) and the same drill as 1.18.0, on copies of that
backup, with no network and no `.env`. All passed:

- Row data matched between the old image and the release image apart from `alembic_version`,
  the two new empty tables (`invites`, `plan_notices`) and `users` (its new columns); the owner
  came out as `admin` with no `closing_on`. Plan tables stayed at 7 versions, 7 sessions and 124
  items, every `user_id` 1.
- Integrity and `foreign_key_check` clean, no `seed.failed`, and the import's diff empty.
- Today, Progress, session times, Review, Plan and Home answered the same on both images; the
  body maps differed only by their new fields (what would add to a muscle, push and pull sets,
  session minutes). The export differed only by the new `plan_notices` table.
- `alembic downgrade b4e8d1f6a9c2` (all four migrations) on another copy matched the backup's
  rows and schema, and the old image ran on the result with the same answers.

Live at 23:58:28 CET by the deploy timer, at a quiet time. The Pi's head is `a9c3e5f7b1d2`, `/healthz`
says 1.19.0 with the bot on, and the first start logged `seed.unchanged` with no `seed.failed`.

## Decisions and where they live

- **Members recover only with the admin's link; `/recover` stays the owner's (Liam, 7 Nov):**
  ADR-0059 addendum; `multi-user-plan.md`, Decided 2026-11-07.
- **A member's erase drops their Telegram link (Liam, 7 Nov):** the same Decided list. Not built
  yet: the code keeps it today.
- **Members' bot messages on at default times; readiness answered on the device, not stored;
  the consent step built now with draft wording (Liam, 7 Nov):** the same Decided list.
- **The walk-through for new people (Liam, 7 Nov):** everything starts at the bottom of its
  ladder, then safety questions, age and how they exercise now, "can you do...?" per movement,
  days, minutes, exercises and kit; approved starters fitted to the answers; the answers kept
  with consent. `any-level-any-time.md`, B5, the owner's answers.

## Open items and next steps

1. **Joining step 8, Telegram for members:** the connect link, the members filter, a session per
   update, and the erase dropping a member's link. #609 does the erase part. A written plan and an independent
   review first: it changes the "the bot answers only the owner" rule.
2. **Step 6, the consent step,** and the walk-through (#577 stage 5), then **step 9**,
   schedules per person.
3. **Waiting on Liam:** new starters for the walk-through, to replace the 2- and 3-day drafts in
   #588 (by days a week and place); rest days; the clinician's and lawyer's lists in #556's body
   before anyone else uses the app.
4. **Follow-ups from the 1.18.0 log** still stand (the warm-up wording, two stale comments, the
   `build-tools` folder choice).
