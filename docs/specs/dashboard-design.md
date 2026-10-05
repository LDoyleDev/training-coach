# Dashboard design (phase 2)

Status: to be designed before phase 2 starts. The design (screens and tokens) is agreed first,
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
