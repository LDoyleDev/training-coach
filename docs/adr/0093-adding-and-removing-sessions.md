# ADR-0093: Adding and removing sessions in your own plan

- Status: Accepted
- Date: 2026-11-10
- Deciders: Liam (20 decisions, 10 Nov 2026: as recommended, except 10 and 15, which he changed)
- Changes: ADR-0034, ADR-0073, ADR-0087, ADR-0091 (addenda there)

## Context

`/plan/edit` (program-builder.md step 6) edits the exercises in a session: add, swap, remove,
sets, range and level, saved as a plan version against the plan's revision. Step 7 asks for the
rest: adding a session, and with it removing one. Nothing in the app can change a plan's sessions
today. The owner can only do it in `plan.toml`, and his import refuses a session missing from the
file (the 1.18.0 known limit). A member is held to their starter's sessions.

Four things make it more than a new row:

- **History names sessions.** `workouts.template_id` is RESTRICT, so a session with logged
  workouts can't be deleted.
- **The queue points at a session** (`plan_state.next_template_id`, `queued`, ADR-0006), and rest
  days are read from the session done last (ADR-0091).
- **Typed logs find a session by its name** (`workout_log._named`, `_session_line`).
- **The body map assumes a 7-day cycle.** `domain.coverage`'s `Day` says so; the starters are
  held to it (`StarterSeed._week`) and the owner's 7 sessions have no rest places. Nothing holds an
  edited plan to it.

The build plan (10 Nov 2026) set out 20 decisions the specs didn't cover, with a recommendation
each. Liam took 18 as recommended. On 10 he wants a cycle change to tell the person, and on 15
he wants the map counted over the cycle's own length.

## Decision

### What the person does

`/plan/edit` gains a **Your cycle** card above the session editor.

- The sessions are listed in queue order, each with its kind and "then N rest days". A week line
  follows ("Your cycle: A, rest, B, rest, C, rest, rest. 7 days.") and the next session is marked.
- **Add a session**: empty or a copy of one of yours, with a name, a kind and "goes after". Each
  is filled in as a suggestion and can be changed.
- Per session: **Up / Down**, **Rest days after** − N + (0-6), **Rename** and **Remove**.
- Before **Save**, a "Saving will" list says what changes: added, removed and moved sessions,
  what's next, and whether today changes. The note is prefilled from the list. Save makes one
  plan version, as now. Nothing changes before it (the app suggests, the person decides).

### The rules (Decided, 10 Nov 2026)

1. **Where a new session goes.** The person picks "goes after". The suggestion is the session
   with the most rest days after it (on a tie, the later one), or the last session when none has
   rest days. The new session takes one of those rest days and the rest are split around it:
   after X with r rest days (r of 1 or more), X keeps ceil((r-1)/2) and the new one gets
   floor((r-1)/2), so the cycle keeps its length. With r = 0 (the owner's sessions today) both
   get 0 and the cycle grows by one day.
2. **What it starts as.** Empty (the picker opens at once; Save still needs one home exercise),
   or a copy of one of your sessions with its home, gym and away versions, kind and optional flag.
3. **Name, focus and kind.**
   - Name: 1-40 characters, unique among your live sessions once normalised. It can't be an
     exercise's name or alias, and it can't read as a date or "today", because typed logs find
     sessions by name. Typed logs and every chooser read live sessions only, so a retired
     session's name can be used again: the old days keep showing the name they were logged
     under, which is the same words, and nothing looks a session up by name across retired rows.
   - Focus: a copy keeps it; an empty session gets its two most-trained muscles in words, at Save.
     It can be edited.
   - Kind: Strength, Cardio or Recovery, preselected from the copy (else Strength), each with a
     line on what it changes. A Cardio session with no single cardio exercise gets a warning, not
     a refusal.
   - Renaming uses the same rules.
4. **A cycle need not be 7 days.** Cycle length is a warning, not a rule. The editor shows the
   cycle's days and, when they aren't 7, says each session comes round less (or more) often than
   once a week. Cardio targets and the review's planned count are compared with the last 7 days,
   so they are scaled to 7 days. The body map is counted per cycle (15).
5. **Removing a session.** If no workout names it, it is **deleted**, so a session added by
   mistake leaves nothing. If a workout does, it is **retired**, as exercises are (ADR-0034):
   `session_templates.retired_on` is set, its items are deleted, and it is parked at
   `position = 10_000 + id`. Its row and name stay, so history still names it. Remove's wording
   says which: "Nothing is logged for it, so it goes" or "Its 14 logged days stay in your
   history". The last session can't be removed. No Put back in the app; the owner's import can
   put one back by slug (14).
6. **A removed session's days go to the session before it** (the last, if it was first), so the
   cycle keeps its length. `rest_after` is capped at 6; beyond that the cycle shrinks and the week
   line says so.
7. **Today's or the next session.** A session in progress refuses the save (409 `in-progress`, as
   now). A session done today can be removed: the workout keeps it as history.
8. **Reordering**: Up / Down. The pointer stays on the same session and the cycle carries on from
   there in the new order.
9. **The queue after a change.** The pointer stays on the session it names, with two exceptions:
   - Its session is removed: the pointer moves to the next live session after it in the old order.
   - A session is added straight after the one done last, before the session the pointer names:
     the new session becomes next.

   `queued` drops removed ids, and `starts_on` is untouched. A rest day today can become a session
   day or the other way round; the "Saving will" list says so first.
10. **A change to the cycle tells the person** (Liam's change: "if there's a change to the
    cycle, it should be notified").
    - What counts: a save that adds, removes, renames, moves or changes the kind or rest days of a
      session. An edit to the exercises inside a session doesn't count.
    - How: a `plan_notices` row (ADR-0087), shown on Home and Plan until "Got it" and sent to
      Telegram once if the bot serves them. For example: "Your plan changed: added Legs 2. Next
      is Legs 2."
    - The text is built from the same list as "Saving will". The owner's import (14) writes one
      too when it adds, retires or puts back a session.
11. **Undo.** A cycle change ends the undo window, as a newer change does. The event
    `plan.cycle_changed` (counts only) is among the kinds `undo._latest` reads, so `/undo` can't
    point the queue at a removed session.
12. **Old ids from the client.** `pick`, the Log page's session choice, a guided start and an AI
    proposal's save refuse a session not in the cycle: "That session is no longer in your plan".
    A proposal can still be saved as an extra. Telegram's Start, Rest and Swap are already safe,
    since they need the pointer.
13. **Limits.** 1 to 10 live sessions, a cycle of at most 14 days, `rest_after` 0-6 and 40 items
    a version, as now. Over a limit, Add is greyed with the reason.
14. **The owner's import** treats `plan.toml` as the whole plan and lists every difference, so
    removals are listed too: "Removes Legs 2: its history stays", retired or deleted as in 5. A
    retired row whose slug `plan.toml` has is listed as "Puts back High intensity". He sees the
    list and decides. This ends the 1.18.0 known limit, and the deploy runbook's rule that
    removing a session needs a data migration.
15. **The body map counts over the cycle's own length** (Liam's change: "the length of the
    plan, length of the cycle").
    - The sets and the days a muscle is trained are counted over the whole cycle, as the code
      does today, and the map says so: "Sets per 8-day cycle".
    - The bands each region is coloured by (program-builder.md Decided 3) are weekly. They are
      stretched to the cycle: a band of 10-20 sets a week is 11.4-22.9 per 8-day cycle. So the
      colours stay true to the weekly evidence and the numbers stay what the cycle really holds.
    - Green's two days a week are stretched the same way: 2 per 7 days of the cycle, rounded
      half up and never under 1 (an 8-day cycle still needs 2 days, a 10-day cycle 3). "On only
      one day a week" becomes "on only one day of your cycle".
    - A 7-day cycle (every plan today) changes nothing.
16. **The map counts what will run**: at the person's `session_minutes` and `session_exercises`
    (`guided.fitted`, as the walk-through's preview does), with "Counted at your 30 minutes a
    session" under it. Empty settings (the owner) change nothing.
17. **Versions of a new session.** An empty session has a home version only: gym empty means
    "done the same way at the gym", away empty means none. A copy copies all three. A member's gym
    swaps aren't applied to a new session, because it isn't a starter's.
18. **The walk-through after an add.** It still replaces the whole plan until the first workout.
    Its plan screen says "This replaces your plan, including the sessions you added" when there
    are any.
19. **One save.** One `POST /api/plan/changes` carries `cycle` and `versions` in one
    transaction: one version and one revision check. A new session and its exercises land
    together.
20. **Wording.** The cycle card, Remove's two wordings, the "Saving will" list and the notice
    text are checked by Liam in the web PRs' screenshots. There is no health wording, so none of
    it goes on #556's clinician list.

### Stored

- **One column: `session_templates.retired_on`**, a nullable date. Empty means in the cycle.
  - It is added with `ADD COLUMN` only: no data changes, no table rebuild.
  - Its downgrade refuses while any row has it set.
  - Every reader of the cycle goes through one helper (`plan_rows.in_cycle()`). Readers of a
    name by id (Home's recent days, the day view, `day_clash`, the AI summary, `undo._name`) keep
    reading retired rows, on purpose.
- **Slugs** for new sessions are made by the server from the name, never in the browser. They are
  unique among all the person's rows, retired ones included, and never equal a starter session's
  slug in `plan.toml`, since `gym_version` decides by slug ("Three days A" becomes
  `three-days-a-2`).
- `plan_edit.revision` adds each session's name, kind, `rest_after` and `retired_on`, so every
  draft open at the release is stale once.

### API

- `GET /api/plan/edit` gains, per session, `kind`, `rest_after`, `optional`, `next` and `logged`
  (workouts naming it), and on the view `limits`.
- `POST /api/plan/changes` and `POST /api/plan/coverage/draft` gain an optional `cycle`: the live
  sessions as they should be, in order. Each entry is an existing `{slug, name, kind, rest_after}`
  or a new `{new: "n1", name, kind, rest_after, copy_of?}`.
  - A session missing from `cycle` is removed, and `versions` may name `new:n1`.
  - Without `cycle` nothing structural changes, so today's web and tests keep working.
  - The answer gains `slugs` (`{"n1": "legs-2"}`).
  - Refusals are 422 in words; 409 `stale` and `in-progress` stay as now.
- `GET /api/plan` gains `rest_after` per session.
- The "Saving will" list is worked out in the browser from a TS copy of `domain/cycle.py`, with
  one JSON of cases shared by both copies, as `walkthrough/day-cases.json` is. The server checks
  it again at Save.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Retire a session with history, delete one without (chosen) | Mirrors exercises (ADR-0034); a mistake leaves nothing | One column, and every cycle reader filtered |
| Refuse to remove a session with history | Smallest | The owner could never remove any of his seven |
| Cycle any length, map per cycle with stretched bands (chosen, Liam) | The owner can add an 8th session; the map shows what the cycle holds | Bands per cycle are less familiar than per week |
| Map scaled to 7 days (recommended) | Weekly numbers as everywhere else | Shows sets the cycle doesn't hold; Liam preferred the cycle |
| Hold every cycle to 7 days | Every count exact | Adding means removing or merging in the same draft |
| A notice on a cycle change (chosen, Liam) | The person sees what changed and what's next, on Telegram too | Tells them what they just did |
| No notice (recommended) | ADR-0087's rule for own edits | Easy to miss that "next" moved |
| One save with `cycle` and `versions` (chosen) | One version, one check; an empty session can't be saved | One larger request body |

## Consequences

- One migration (`retired_on`): the release that carries it changes the live file, so it needs
  Liam's OK naming it, a backup and a dry run on a copy.
- Seven code PRs after this one:
  1. the db and every cycle reader;
  2. `domain/cycle.py` and the map's cycle bands;
  3. `plan_edit.save` with the cycle, the notice and the undo barrier;
  4. the import;
  5. the API;
  6. and 7. two web PRs.
- Tests that must hold:
  - a retired session is offered by no route (Today, the week ahead, the pick menu, the Log page,
    Plan, the map, Progress, Review, a typed log, the MCP summary), but its old days still show
    its name;
  - one person's add and remove leave another's plan alone (`test_two_people_plans.py`);
  - a cycle change writes one notice, and an item edit writes none.
- `plans-per-person.md`'s "Writes", ADR-0091's "every existing session has 0" and the deploy
  runbook's line on removing a session are brought up to date here.
