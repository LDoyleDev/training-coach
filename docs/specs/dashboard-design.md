# Dashboard design (phase 2)

Status: D1 decided for the guided session on 2026-10-09 (below). The other screens (Today, Progress,
Week, Body) stand as in the clickable mockup unless Liam changes them. The design is agreed first,
then built to match.

Screens: Today, Plan (week and ladders), Progress (per exercise charts), Baseline vs retests,
Measurements, Share view (read-only, no measurements or photos).

Constraints: phone-first, works inside Telegram as a Mini App (respect Telegram theme
colours), dark and light mode, CSP without inline scripts, fast on mobile networks.

## Plan screen (built)

Now its own page again, `/plan`, in the nav (ADR-0069; it was the Plan tab of Progress, ux-flow-plan D2),
behind sign-in like every page (ADR-0041); it was the public root page. It is a
read-only view of the training plan from `GET /api/plan`: the
seven-session cycle, each session's exercises and starting variations, weekly sets per muscle
against Galpin's 10-20 range, progression ladders, and a preview of the Telegram flow. It holds
no personal data (no logs, measurements or photos), so it is safe to share.

Visual system: chalk and cast iron, one accent taken from the pink of an 8 kg competition
kettlebell; one typeface (Archivo, self-hosted for the CSP) using its condensed widths for
headings and figures. The ring draws once on load; reduced motion is respected.

## Guided session (decided 2026-10-09, D1)

Starting a session from Today walks through it one set at a time. Agreed on a clickable mockup
(the "Guided session" screen in Liam's app mockup), with these choices:

1. **Overview to confirm:** the session, about how long it takes, the warm-up reminder, and the
   pairs (ADR-0031) with each exercise's step and sets × target. Start session, or Resume.
2. **One set per screen, in work order**, always open, top to bottom (Liam, 2026-10-25): the
   exercise and its step, "Do <other> first" before a pair has started (it swaps the pair for
   this session), then the counter: "Set 2 of 4" and the target, and Confirm set.
   - Reps: one big number starting at the target, with − and +.
   - One-sided exercises: one number for "each side"; "Left and right differ" splits it.
   - Timed exercises: a stopwatch, adjustable by ±5 s after stopping.
   - Under the counter, the short how-to (#116); then, for an exercise with a drawn figure, its
     moving mannequin (ADR-0063), always shown; then the muscles it works in words ("Works:
     Lats · helped by upper back, biceps · a little: rear delts, forearms"), beside small front
     and back figures coloured by the catalogue weights on the session map's colours (ADR-0064,
     ADR-0069).
   - The screen stays on through the sets and rests (wake lock, where the browser has one).
3. **Confirm set** starts a **rest countdown** (by transition, ADR-0065; +15 s, Skip) showing
   the next set. Its last 3 seconds count softly and its end plays the timer sound chosen in
   Settings (ADR-0062), and the phone buzzes. Skip plays nothing. Back fixes the previous set.
4. **Leave keeps the place:** progress is kept on the server, so the session resumes on any
   device. One not saved by the end of the day is offered for saving the next morning.
5. **Check and save:** every exercise's sets against targets; nothing is saved until Save
   session. At the top, the time so far split into sets, rests and breaks (ADR-0061); under
   each exercise's reps, each set's seconds ("34s / 31s / 38s"). A set at least half again as
   long as the median of the exercise's other sets (and 10 s more) is bold, and a rest that ran
   30 s or more over its plan says so on the set after it ("+40s rest"). Sets without times
   show none. The save goes through the same service as a typed log (`workout_log`, step 1-E):
   the server re-checks the target session, block, queue and every set's value and bounds, so
   nothing from the browser is trusted. The session API is owner-only behind 2-F login (#115).
6. **Saved:** new bests, the next session, and stretching 10/20/30 (ADR-0032).

Issues: 2-F login #115 (first), exercise summaries #116, the API #117, the screens #118.
