# Session log: 10-11 Nov 2026 (1.22.0): adding and removing sessions

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-10-the-walk-through.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.22.0 | Adding and removing a session (ADR-0093, #577 stage 4, its last part): #714 retired sessions and every reader of the cycle through one helper (`session_templates.retired_on`; migration `b3d5f7a9c1e4`), #712 a cycle draft applied, the queue after it and the map's bands per cycle, #719 a plan saves its sessions (add, copy, rename, move, remove), #720 a removed session refused in words and ending undo, #721 one cycle-change event kind for undo, #724 the import removes and puts back sessions with history kept, #725 the cycle in the plan editor's routes and the map per cycle; on the web #716 the cycle rules in TypeScript held to the shared cases, #728 Your cycle on the plan editor (add a session, rename, rest days), #729 move and remove with what saving will do, #731 what's next and what today becomes, #733 a cardio session without its cardio exercise warned, #734 a session's kind changed on the card. Docs: #707 (ADR-0093), #711. |

Released with Liam's OK in chat (11 Nov, naming the release). Before the release PR was merged:
a manual backup (`training_coach-manual-20261111T220221Z.db`) and the same drill as 1.21.0, on
copies of that backup, with no network and no `.env`. All passed:

- Row data matched between the old image and the release image apart from what the release
  means to change: `session_templates` gains `retired_on`, empty on all 7 rows, and its rows
  are otherwise identical. Plan tables stayed at 7 versions, 7 sessions and 124 items, every
  `user_id` 1.
- Integrity and `foreign_key_check` clean, no `seed.failed`, and the import's diff empty.
- Today, Progress, session times, Review, Plan, both body maps, Home, the import and the
  walk-through answered 200 on both images. Plan differs only by each session's new
  `rest_after`, the body maps by their new `cycle_days`, `session_exercises` and
  `session_minutes`, and the walk-through by its `revision`, a hash that now also covers rest
  days and the retired day (a tab left open over the deploy is asked to reload once). The
  export differed only by the new column.
- `alembic downgrade a1c3e5f7b9d2` on another copy matched the backup's schema and rows exactly,
  and the old image started on it with no `seed.failed` and answered the same.

Live at 23:36:02 CET by the deploy timer. The Pi's head is `b3d5f7a9c1e4`, `/healthz` says
1.22.0 with the bot on, the first start logged `seed.unchanged` with no errors, and the live rows
match the drill: integrity and foreign keys clean, plan tables at 7, 7 and 124, `retired_on` in
place with no session retired, and no plan notice yet. The owner's cycle is untouched; adding,
moving and removing sessions is his to try from Plan, Edit.

## Decisions and where they live

- **Adding and removing a session, 20 decisions (Liam, 10 Nov):** ADR-0093 and its five
  addenda (the guards, the import, the API's shapes, "Saving will", the Cardio warning).

## Open items and next steps

1. **#577:** stage 4 is done. Left: stage 6's switch and stage 7 (the first real person), both
   Liam's.
2. **Waiting on Liam:** turning on `TC_MULTI_USER` (with the notice in the app and the DPIA's
   open items, multi-user-plan step 11); the clinician's and lawyer's lists in #556's body
   before anyone outside family and friends; the Dependabot PRs (#660's Gradle plugin needs its
   verification metadata trusted); a look at the cycle card's wording on the phone.
3. **Follow-ups:** after the owner's own erase his scheduled messages restart at the default
   times (from the 1.20.0 log, unchecked); the easy start (B6). The follow-ups from the 1.18.0
   log still stand.
