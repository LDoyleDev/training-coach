# Session log: 31 Oct 2026 (1.11.0): short on time today, step levels, stop signs, the Europe gate

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-30-level-questions-step5-prep.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.11.0 (released with this log's PR open) | #495 the decisions (ADR-0082 to ADR-0085) and the research (`any-level-research.md` Parts 1-4); #502 `domain/trim.py`; #501 a shorter day judged on its own planned sets; #509 each guided day's plan saved (`workouts.minutes`, `workouts.planned`) and used by targets and Move up; #510 `PUT /api/session/length` and the trimmed guided session, ramp sets at 30 minutes or less, the person's pace; #516 As planned · 40 · 30 · 20 on Today, Keep, what's dropped, the shortest; #517 the bot's work list and morning message follow the length; #505 stop signs before the first session and one tap away, "Use the talk test, not heart-rate zones", the breathing cue once a session; #506 a level (1-6), marks and `failure_ok` on every step; #513 the 451 page outside the EU and EEA (`CF-IPCountry` through a trusted proxy, fails open without the header); #493 pyasn1 CVE fix. Migrations add columns only (`c3f7a1e5d9b2`, `face6f88f5fe`, `c3e8a1f5d7b2`, `d4f9b2a6e8c1`); the seed fills the levels on start. |

## Decisions and where they live

- **Liam's nine decisions of 31 Oct:** `any-level-any-time.md`, "Decided". Both ways to set the
  time, the trim's order, ramp sets in very short sessions, the optional last set (F2), six
  levels with an open top, lower steps by extending ladders plus easier exercises for the same
  muscles, four preferences that are not medical, safety questions fit for Europe and an app
  for the EU and EEA only, written starting starters, the build order.
- **ADR-0082** time; **ADR-0083** levels, lower steps, preferences; **ADR-0084** short days, the
  last set, stepping down, the easy start; **ADR-0085** safety questions answered on the device
  (supersedes ADR-0046's stored answers) and the four-layer Europe gate. Amended: ADR-0016,
  0027, 0028, 0046, 0065 (status lines).
- **Reviewed before building:** a plan critic and a walk-through as four people (frail 78, 140 kg
  beginner, trained with 20 minutes, on beta-blockers); the ADRs and the catalogue list were
  revised after both (`any-level-any-time.md`, "B2-B3 revised after the evals").

## State at the wrap

- **Pi.** 1.10.0 live; 1.11.0 deploys about 15 minutes after its release.
- **Open PRs:** #514 and #515 (the Europe gate's last-seen date, the bot and MCP 30-day window,
  residence on Account) wait for Liam's Cloudflare check below. #484 (starters) waits for Liam.
- **In progress:** entry exercises (#507); next the ladders' downward migration (#508), then
  minutes per session, stepping down and the last set, then setup.

## Open items and next steps

1. **Waiting on Liam:**
   - **Cloudflare, before #514 merges:** check that `CF-IPCountry` reaches the app (Network → IP
     Geolocation on). Without it the bot and his AI pause 30 days after #514's release. Then
     apply the WAF rule in `docs/runbooks/deploy.md` (after #513, it is there).
   - Whether the bot's 30-day check may sit in a first handler rather than `owner_only` (#514
     edits ADR-0085's wording); the band reader's import isn't exempt, so band data pauses
     outside Europe.
   - The levels and `failure_ok` calls listed in #506's body; a fifth preference, "Easy on my
     knees" (ADR-0083, from the walk-through); "Europe" as EU + EEA without the UK and
     Switzerland; the 30-day travel window.
   - A clinician for the stop signs, safety questions and notes; a lawyer for ADR-0085's points,
     before anyone but Liam uses the app.
   - Earlier items still open: the starters (#484), test-day warm-up, the level questions'
     choices, the phone adb check, step 5 from about 4 Nov, the restore drill.
2. **The downward migration (#508)** moves ladder positions: its release needs a Pi check, a
   backup, a dry run on a copy and Liam's OK.
3. **`readiness_answers`** goes with ADR-0085's on-device questions (builder step 10); dropping
   the table needs Liam's OK.
