# Session log: 5-7 Nov 2026 (1.18.0): plans per person

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-05-reverse-fly-dumbbells.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.18.0 | Builder step 5. #578 tests that pin erase and the old migrations; #579 the Plan page and body map read rows, not `plan.toml`; #580 the flip: sessions, their items and plan versions belong to a person (migration `b4e8d1f6a9c2`); #581 the owner saves a `plan.toml` change as one version, from a card on the Plan page; #573, #575, #576 docs. |

Released with Liam's OK in chat (7 Nov). Before the release PR was merged, with no session open:
a manual backup (`training_coach-manual-20261107T063713Z.db`) and the drill the spec asks for, on
copies of that backup, with no network and no `.env`. All passed:

- Row data in all 40 tables matched between the old image and the release image, apart from
  `alembic_version`; plan tables stayed at 7 versions, 7 sessions and 124 items, every `user_id` 1.
- Integrity and `foreign_key_check` clean, no `seed.failed`, and the import's diff empty.
- Today, Progress, session times, Review, Plan, both body maps and Home answered the same on both
  images. The export differed only as intended: sessions and plan versions moved from its
  reference section to the person's own tables.
- `alembic downgrade -1` on another copy matched the backup's rows and schema, and the old image
  ran on the result with the same answers.

The first run of the drill didn't count and was redone: the Pi's `docker compose cp` has no `-q`,
so the copies failed and the containers started empty. The script now stops if a copy is missing.

Live at 07:58:55 CET, chosen at a quiet time. The Pi's head is `b4e8d1f6a9c2`, the live plan rows
match the drill's counts, and the first start logged `seed.unchanged` with no `seed.failed`.

## Decisions and where they live

- **One database, a `user_id` on each row (Liam left it to the build, 6 Nov):** ADR-0073 addendum.
- **Nobody gets a copy of the owner's plan; the migration refuses if anyone else exists, and the
  import is the owner's alone (Liam, 5-6 Nov):** `plans-per-person.md`, Decided.
- **New people are walked through finding their level and exercises, then get a plan (Liam, 6
  Nov):** the roadmap, #577. Assumed, not yet confirmed: they start from a suggested starter they
  can change, not a blank plan.
- **People manage their own plans and are told when something changes in the background (Liam, 6
  Nov):** #577, stage 2.
- **Lengths offered only when shorter than the session (Liam, 7 Nov):** ADR-0082 addendum, for the
  next release. The HIIT estimate moves from about 1 minute to 30 s a round with it.

## Open items and next steps

1. **The roadmap, #577.** Stages 2 and 3 and the live map are built on PRs #582, #583 and #584,
   held until this release. The notices migration (`d7a3f9c1e5b8`) makes the next release one that
   changes live data, so it needs Liam's OK, a backup and a dry run on a copy.
2. **Waiting on Liam:**
   - Whether "from scratch" means a suggested starter, as assumed above.
   - The new starting starters, before they ship.
   - **Before anyone else uses the app:** the clinician's and lawyer's lists in #556's body, which
     may cost money.
   - The away versions (#539) and knees marks (#541, #546) to look over.
   - Optional: an automation that opens Mi Fitness daily, so heart rate isn't held back.
   - `draft/traps-rear-delts` (local only, superseded by the face pulls): keep or delete. The
     remote branches `feat/507-entry-figures-a` and `-b` are his to delete, if he wants.
3. **Known limit:** a session the owner adds in the app that isn't in `plan.toml` blocks the
   import. It can't happen until the editor can add a session (#577, stage 4). Closed by #722
   (ADR-0093 Decided 14): the import lists such a session as removed instead.
4. **Follow-ups:** the Tests page could say "about 10 minutes" for the warm-up;
   `api/settings.py` and `db/models.py` comments still say "where it's safe"; the APK guard and
   the release job take the highest `build-tools` folder, which could be a preview.
