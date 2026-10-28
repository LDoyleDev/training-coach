# ADR-0075: Move up, Not yet and any level by hand, on the web

- Status: Accepted; a level can also be changed during a session, for today or from now on (ADR-0080)
- Date: 2026-10-25
- Deciders: Liam

## Context

Moving up a ladder only happened in Telegram: the Move up / Not yet prompt after a saved session
or on /progress (ADR-0016, ADR-0025). The web app showed "Ready to move up" as plain text on
Progress, Home, the saved screen and the weekly review, with nowhere to act on it. Liam asked
(25 Oct 2026) for that text to be a button that takes him to where the program's difficulty is
changed. He chose Move up / Not yet **and** choosing any level by hand, down as well as up, on
the web, now. The program builder already planned a level set by hand on the Plan tab
(`program-builder.md`, G).

## Decision

- **The Plan page gets a ladder panel per exercise** ("Your levels", above the plan): every step
  with the current one marked, the last session and best at that step, and the next step's name
  (and cue, where a step has one). It lists the exercises ready to move up, and the one a link
  asked for; "Show all exercises" lists the rest. Retired exercises (#107) aren't listed.
- **Move up and Not yet on the web use the bot's rules and service.** `POST
  /api/progress/{slug}/move-up` takes the step the page showed and calls `progress.move_up`,
  which checks again that the exercise is still on that step, still ready and has a next step
  (ADR-0025), so a stale or forged press changes nothing. In a strength block it waits and says
  why, as the bot does (ADR-0028). `POST /api/progress/{slug}/not-yet` records
  `progress.not_yet`, but only while the exercise is still on that step.
- **Any level by hand.** "Change level" picks any step of the exercise's own ladder, up or down,
  after a confirm: "Targets for <step> start fresh from its own history." `POST
  /api/progress/{slug}/level` sets it and records `progress.level_set` with the exercise and the
  from and to step ids. It never needs "ready", **and it is allowed in a strength block**: the
  block holds the rule's suggestion, not the person's own choice. A step of another exercise is
  refused (422). Targets then come from that step's own history (ADR-0034), so going back down
  picks up where that step was left.
- **Every "Ready to move up" links to `/plan?move=<slug>`**, which opens and scrolls to that
  panel: Progress (each exercise's status, and the count in the intro), Home (one link per
  exercise), the saved screen line and the weekly review. Those responses now carry each
  exercise's slug.
- **Telegram stays as it is.** A prompt pressed after a move on the web answers "already moved on
  since that message", by the check it already had.
- All three routes are owner-only (ADR-0036) and use the session bound to the person (ADR-0029).
- "Ladder steps climbed" on Home still counts Move ups only, not levels set by hand.

This amends ADR-0016 and ADR-0025: moving up is no longer only the bot's prompt, and the step can
also be set by hand.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Move up / Not yet and any level by hand, on the web (chosen) | One place to change difficulty; going back down is possible; same rules as the bot | Two ways to change a step to keep in step; a hand-set level skips the rule |
| Move up / Not yet only | Smallest change; the rule always decides | No way down after a bad week or an injury; wait for the builder (step 6) |
| Links only, act in Telegram | No new routes | The button still sends you somewhere you can't act |

## Consequences

- `progress.level_set` is a new event kind next to `progress.moved_up` and `progress.not_yet`.
- `GET /api/progress` gains `slug`, `step_id` and `ladder` per exercise and `strength_block`;
  Home's and the review's `ready` become `{exercise, slug}`; a saved session's earned rows gain
  `slug`.
- The program builder's G ("set by hand on the Plan tab") is done; the "Can you do ...?"
  questions (G1) and the suggestions from tests (G2) are still to come.
- When plans become per person (ADR-0073) the routes stay as they are: the step is already per
  person (`exercise_state`).
