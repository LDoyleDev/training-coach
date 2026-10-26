# Session log: 26 Oct 2026 (1.2.0): body measurements, home kit, kit ladders and 7-day totals

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-25-session-screen-bell-stretching.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.2.0 (released with this log) | #349 one way to take each measurement, a tape body-fat estimate and a re-measure warning; #351 the Body page: how to measure, the 7-day weight average and a body-fat trend, still working when one of them fails to load; #356 leg figures for hamstring curl, calf raise, jump squat, tibialis raise, pistol, single-leg RDL and reverse Nordic; #358 home kit per person, steps lock by kit, the AI hears "top for my kit" only at the top of the range; #359 My equipment on Account, locked steps and "Top for your kit" on levels and Progress; #360 concrete kit ladders with step cues and band strengths; #364 the cardio card, Home and the bot's "Counted" reply count the last 7 days, and Home adds moderate minutes to zone 2; #362 and #363 flaky rest-timer and stretching tests fixed; this log |

## Decisions and where they live

- **Body measurements:** one protocol per measurement, a tape estimate that is off unless the
  person turns it on, and a warning when a value looks like a re-measure (ADR-0076).
- **Home kit:** a kit per person; a step that needs kit not listed is locked, Move up skips to
  the next open step, and a level can still be chosen by hand with a warning. No kit listed
  means nothing locks (ADR-0071, Built). The AI guide is version 3 (`docs/ai-guide.md`).
- **Kit ladders:** accepted as proposed (Liam, 25 Oct), curl and triceps with an 8 kg middle
  step: vague top steps renamed in place and the rest appended, so nobody's place moves
  (`docs/specs/kit-ladder-proposal.md`, ADR-0071).
- **Running totals:** the cardio card, Home's card and the bot's "Counted" reply count today
  and the six days before, so a Monday still shows the weekend; the weekly review stays Monday
  to Sunday; HIIT, logged in rounds, stays out of minutes totals (ADR-0077, Liam, 26 Oct).

## State at the wrap

- **Pi.** v1.1.0 live since 01:07 on 26 Oct; 1.2.0 deploys within about 15 minutes of its
  release PR merging (ADR-0030).
- **Backups.** The nightly backup ran at 03:30 on 26 Oct. The 04:30 off-site run isn't visible
  to the read-only key (`tc-read` shows app logs only), so it is unchecked here.
- **Band data.** None since 2026-10-19.

## Open items and next steps

1. **Off-site backup:** check the first scheduled run (04:30, 26 Oct) in Healthchecks and the
   bucket; the first upload's 501 from R2 is a watch item.
2. **Band:** Liam's sync on reader 0.0.3 decides between the Health Connect reader and
   Gadgetbridge (ADR-0070).
3. **Liam:** list the home kit under My equipment on Account; until then no step locks.
4. **Next builds:** figures for the new kit set-ups (the proposal's Figures section: vest or
   backpack, dip bars, hammer curl, suitcase split squat); the Copenhagen plank front view
   needs a decision; the calf-raise figure reads weakly. Then builder steps 8 (load, ADR-0072)
   and 9 (home or gym).
5. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
6. **Follow-ups:** the reader closing when the screen turns off (debug over adb); Gradle
   dependency verification; `/healthz` shows the version publicly; a Dependabot ignore rule for
   Node majors.
