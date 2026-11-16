# ADR-0094: The easy start: two light weeks, then one set lower for four

- Status: Proposed
- Date: 2026-11-16
- Deciders: Liam (the decisions below, each with a recommendation)
- Changes: ADR-0082, ADR-0084 and ADR-0092 (an addendum in each once accepted)

## Context

ADR-0084 accepted an easy start "for a person at level 3 or below, or who says they're new to
training": the first two weeks run three or four exercises of one or two sets (ICFSR 2021), then
program-builder's Decided 7, one set lower per exercise for four weeks (a single set stays one).
A trained person skips it. `any-level-any-time.md` B6 adds 5-10 minutes of walking on top. ADR-0092
(Decided 12) left it out of the walk-through and said the walk-through then offers it as a switch.
None of it is built: no code reads a person's first weeks except the last-set lock
(`domain/last_set.py`, 8 weeks from the first logged workout).

The evidence is about soreness, not adherence. An easy first bout protects against the damage of
a harder one for about two weeks, gone by three (Chen and Nosaka, small studies, research file
"Muscle soreness, the repeated-bout effect"). No trial shows an easy start keeps people training
(weak). Eccentric-heavy work in a novice's first weeks is the rhabdomyolysis pattern (case reports,
weak).

What the specs leave open: what the switch changes in a session, from which day the weeks count,
who it is offered to and whether it is on by default, how it ends, what the map and Plan show
while it runs, and where it is stored. The product rule holds: the app suggests, the person
decides. A switch the walk-through turns on is a suggestion shown before Save, as every value
there is (ADR-0092).

The starters (`plan.toml`) have 5 to 10 exercises a session at 2 to 4 sets, and no cardio item.
The trim (`domain/trim.py`, ADR-0082) already cuts a day by exercises per session first, then
sets, then whole exercises by its drop key, and every day view (Today, the guided session, the
bot, the map at that length) goes through it.

## Decision (proposed)

The easy start is a per-person setting. While it runs, the trim applies a stricter cap before the
person's own minutes and exercises per session:

- **Weeks 1-2 (the easy weeks):** at most 4 exercises, at most 2 sets each. Which exercises go is
  the trim's drop key (covered accessory work first, main patterns no other exercise trains last).
  The overview says it once: "Easy start, week 1 of 2: four exercises, two sets each. Then a
  5-10 minute walk, if you like." The walk isn't tracked.
- **Weeks 3-6 (one set lower):** every exercise as planned, one set fewer; a single set stays one.
  The overview says "Easy start, week 3 of 6: one set fewer of each".
- **The weeks count from the first logged workout,** the day the last-set lock counts from, so a
  person who starts late still gets them.
- **Then it ends by itself** with a notice on Today and Telegram: "Your easy start is done: full
  sessions from today", with "One more easy week" on it, which repeats the week it ended on.
- Planned sets for Move up and Step down are the day's trimmed sets, as on a short day (ADR-0084),
  so an easy day counts toward Move up on the sets it planned.
- The map and Plan show the plan as it is, not the easy weeks, with one line: "The first 6 weeks
  are lighter (easy start)."

Stored as `settings.easy_start` (a boolean, off by default) and
`settings.easy_start_extra` (weeks added, 0 by default): one migration, so its release changes
live data.

## Decisions for Liam

Each has a recommendation, and the Decision above follows them. Answer by number.

1. **Two phases or one.** ADR-0084 accepted two easy weeks then four weeks one set lower.
   *Recommended:* both, as accepted. *Or:* the two easy weeks only (simpler, and Decided 7's four
   weeks have no study of their own behind them).
2. **The easy weeks' size:** "three or four exercises of one or two sets". *Recommended:* 4
   exercises, 2 sets: 8 sets a session. *Or:* 3
   exercises; or 1 set in week 1 and 2 in week 2.
3. **Which exercises stay:** *Recommended:* the trim's drop key, the same rule as a short day, so
   the main patterns stay. *Or:* the first four in the session's order.
4. **Who is offered it:** *Recommended:* everyone in the walk-through, on screen 13 as a switch,
   turned on (marked "suggested") at a suggested level of 3 or below and off at 4. ADR-0084's
   "new to training" is covered: exercising under once a week gives level 2, and 1-2 times gives
   3. *Or:* only at level 3 or below, with no switch for a level 4.
5. **Where else it can be turned on:** *Recommended:* Account too, until the first workout is
   logged, as the walk-through can be run again until then (ADR-0092 Decided 13). After that it can
   only be turned off: someone who finds the sessions hard later has Step down and Ease back in.
   *Or:* Account at any time, which restarts the six weeks.
6. **The day the weeks count from:** *Recommended:* the first logged workout. *Or:* the plan's
   start day (`plan_state.starts_on`), which can pass with nothing done.
7. **Days or sessions:** *Recommended:* calendar weeks, as the evidence counts them (the
   protection fades in about two weeks whether or not you train). *Or:* the first 4-6 sessions,
   which fits a 2-day plan better.
8. **How it ends:** *Recommended:* by itself after week 6, with the notice and "One more easy
   week" (the person decides, and a full session never comes as a surprise). *Or:* a prompt at
   the end of week 2 asking before one set lower begins; or no notice.
9. **A gap during the easy start:** *Recommended:* nothing new. After 21 days or more away, Ease
   back in already offers a step down, and the weeks keep counting. *Or:* pause the weeks during a
   gap.
10. **Move up during the easy weeks:** *Recommended:* offered as usual on the sets the day
    planned. Fewer sets don't make a step harder, and the walk-through placed each step where
    the person said they could do it. *Or:* held until the easy weeks are over.
11. **What the map and Plan show:** *Recommended:* the plan as it is, with the one line. *Or:*
    the map at the easy weeks, which would show much of the body under its bands for two weeks
    and read as a worse plan.
12. **The walk:** *Recommended:* one line on the overview, not tracked, like screen 13's line
    about the balance and sit-to-stand snack for 65 and over. *Or:* a cardio item added to
    each session for six weeks, which then counts on the map.
13. **The owner:** *Recommended:* never offered; the 7-day cycle is a trained person's, and
    `/start` stays a try-out. *Or:* on Account for the owner too.
14. **The bot:** *Recommended:* the morning message names the easy-start week in the same words
    as the overview, and the end notice goes on Telegram once (the plan-notice path, ADR-0087).
    *Or:* the web only.
15. **The re-check every 6-12 weeks (B6):** *Recommended:* not in this ADR; its own item later.
    *Or:* include it here.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A cap in the trim, by setting and date (proposed) | One rule in `domain/trim.py`, at 100% coverage; every day view gets it; the plan isn't rewritten and nothing to undo | The trim gains a third input; Plan shows more than the person does for six weeks (the line explains) |
| Write a light plan version for six weeks, then restore | Plan and the map show exactly what's done | Two plan versions the person didn't make; a restore that can clash with their own edits (ADR-0093) |
| Fill exercises per session and minutes for two weeks, then clear them | No new rule | Overwrites the person's own settings; no set cap; nothing to say why |
| No easy start, Step down only | Nothing to build | Against ADR-0084 as accepted; Step down comes after two missed sessions, the soreness first |

## Consequences

- `domain/trim.py` takes the easy-start week (none, easy, one set lower) and applies its cap before
  exercises per session and the minutes; table tests for each week and with each setting.
- A pure `domain/easy_start.py` works out the week from the first workout, the extra weeks and
  today, like `last_set.available`.
- One migration (`settings.easy_start`, `settings.easy_start_extra`), so the release changes live
  data: Liam's OK, a backup and a drill on a copy.
- The walk-through's screen 13 and Save gain the switch (TS, with the browser's level rule), and
  the preview shows the plan with the line; Account gains the switch.
- The end notice is a plan notice (ADR-0087: shown until seen, told on Telegram once), written
  the first day after week 6; Today's card carries "One more easy week".
- The export includes the two settings. Nothing changes for the owner.
- `any-level-any-time.md` B6's status line points here.
