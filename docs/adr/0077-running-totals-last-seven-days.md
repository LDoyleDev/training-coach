# ADR-0077: Running totals are the last 7 days; the weekly review stays a calendar week

- Status: Accepted
- Date: 2026-10-26
- Deciders: Liam

## Context

Liam (26 Oct 2026): "My cardio is not showing as adding up on the cardio section ... change the
this week totals to the last 7 days. That's the piece that's important, rather than this
calendar week."

Three totals counted Monday to today: Home's "This week" card, the Cardio card's "This week"
line, and the zone 2 line after counting a band workout (the web's band offers and the bot's
"Counted." reply). Under Home's card, the "Last 7 days" list was already rolling. So on a Monday
the list showed the weekend's cardio and the card said about 0. Home's card also added only zone
2: moderate cardio was in the list with its minutes and never in the total.

## Decision

- **Running totals count the last 7 days: today and the six days before, in local time.** One
  helper, `review.last_days(on)` with `review.LAST_DAYS = 7`, gives the first of those days;
  Home's list and card, and `cardio.week`, all use it.
- **Home's card is "Last 7 days"**: planned sessions done (each once) and extras, zone 2 and
  moderate minutes, and personal bests, over the same 7 days as its list, so the two agree. It
  shows moderate next to zone 2 (", 35 moderate"), as the Cardio card does, so the minutes in
  the list add up to the card. `HomeWeekView` gains `moderate_minutes`; `start` is the first of
  the 7 days.
- **The Cardio card, the band offer's reply and the bot's "Counted." reply** say "Last 7 days" /
  "in the last 7 days" for the same minutes.
- **The zone 2 target (180-200 a week) reads against the last 7 days.** Seven days are a week,
  so the target is unchanged.
- **The weekly review stays Monday to Sunday** (D6 in `docs/specs/phase-2-decisions.md`): the
  Review page, the bot's Sunday review, its AI comment and the habits' "days this week". It is a
  look back at a calendar week, not a running total. All-time cardio minutes are unchanged.
- HIIT logs rounds, not minutes, so it stays out of every minutes total; the labels say "zone
  2" and "moderate", not "cardio".

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A (chosen): running totals over the last 7 days, review stays a calendar week | A Monday still shows the weekend; the card agrees with the list under it | Two meanings of "week" in the app, each labelled |
| B: everything, the review included, over the last 7 days | One meaning of "week" | The review would cover different days each time it is opened, earlier weeks lose a fixed start, and D6 chose a calendar week for the look back |
| C: keep the calendar week, add the weekend as a note | Small change | The total still drops to 0 on Mondays, which is what was reported |

## Consequences

- `review.span(session, start, end)` counts sessions, minutes and bests for any range; the
  weekly review uses it for its week, Home for its 7 days.
- "This week" still labels the weekly review, the habits and the Plan's body map (what the plan
  gives each muscle in a week). A running total labelled "this week" is a bug.
- `ux-flow-plan.md` (A1, B1) points here for what the totals count.
