# Dashboard design (phase 2)

Status: D1 decided for the guided session on 2026-10-09 (below). The other screens (Today, Progress,
Week, Body) stand as in the clickable mockup unless Liam changes them. The design is agreed first,
then built to match.

Screens: Today, Plan (week and ladders), Progress (per exercise charts), Baseline vs retests,
Measurements, Share view (read-only, no measurements or photos).

Constraints: phone-first, works inside Telegram as a Mini App (respect Telegram theme
colours), dark and light mode, CSP without inline scripts, fast on mobile networks.

## Plan screen (built)

The public root page (`/`) is a read-only view of the training plan from `GET /api/plan`: the
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
2. **One set per screen, in work order:** exercise, step and a short how-to (#116); "Set 2 of 4"
   and the target.
   - Reps: one big number starting at the target, with − and +.
   - One-sided exercises: one number for "each side"; "Left and right differ" splits it.
   - Timed exercises: a stopwatch, adjustable by ±5 s after stopping.
   - Before a pair has started: "Do <other> first" swaps the pair for this session.
3. **Confirm set** starts a **rest countdown** (60 s default, +15 s, Skip; the phone buzzes at
   the end) showing the next set. Back fixes the previous set.
4. **Leave keeps the place:** progress is kept on the server, so the session resumes on any
   device. One not saved by the end of the day is offered for saving the next morning.
5. **Check and save:** every exercise's sets against targets; nothing is saved until Save
   session. It saves through the same rules as a typed log (ADR-0007).
6. **Saved:** new bests, the next session, and stretching 10/20/30 (ADR-0032).

Issues: 2-F login #115 (first), exercise summaries #116, the API #117, the screens #118.
