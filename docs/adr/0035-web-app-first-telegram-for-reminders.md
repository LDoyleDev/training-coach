# ADR-0035: The web app is the main surface; Telegram is for reminders

- Status: Accepted
- Date: 2026-10-09
- Deciders: Liam

## Context

Phase 1 put everything in Telegram. The guided session (D1, `dashboard-design.md`) showed a
flow that Telegram messages can't do well: one set per screen, big + and − buttons, a rest
timer, a stopwatch, resume on another device. Liam: "the web app is where we should be
focusing the user journey".

## Decision

- **The web app is the main surface:** today's session, the guided session, logging, progress,
  the week, body and settings. New user-facing features are designed for it first.
- **Telegram stays as a background piece:**
  - morning and evening reminders, which reach the phone with no app installed;
  - quick logging by text or voice, as now;
  - the first sign-in and recovery link (ADR-0036).
- Existing Telegram features keep working; nothing is removed for now. Features that only make
  sense on a screen (guided session, charts) are not built in Telegram.
- Web push may take over reminders later: it works on Android, and on iPhone once the app is
  added to the home screen. That is a separate decision.
- The same web app is the basis for a phone app later: wrapped as an Android app (a trusted
  web activity) first, with native work only where it pays.

## Consequences

- 2-F sign-in (#115) comes first: no personal web screen exists without it.
- The product spec's "everything doable from Telegram" no longer holds for new features.
- `bot/` stays a thin adapter over `services/`, as does `api/`, so both surfaces share one set of
  rules.
