# ADR-0026: Built for one, designed for many

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam

## Context

Phase 1 is built for one person: one allowed Telegram user (ADR-0009), one plan, no user ids in
the schema. On 2026-10-07 Liam decided the app should become available to other people in the
end; that the web app (and later a phone app) should do everything the bot does; Android first
with iPhone kept possible; and no spending for now. Options and research:
`docs/specs/platform-and-health-data-proposal.md` (section 0 records his answers; its other
questions are still open and are not decided here).

## Decision

- **Telegram is one surface among several.** The web app gets everything the bot does; logic stays
  in `services/` and `domain/` (import-linter enforces it), so a new surface adds adapters only.
- **Multi-user ready from the next schema change.** A `users` table (Liam as the only row) and a
  `user_id` on every per-person table, with every query scoped by it and a test that enforces
  it. Single-user behaviour stays until invites exist.
- **Zero spend until decided otherwise:** no paid APIs, aggregators, store fees or subscriptions.
  Health data comes in through free, on-phone routes first (Android Health Connect).
- **Stays a fitness app:** no diagnoses or medical advice (EU Medical Device Regulation).

Not decided here: how people sign in without Telegram (passkeys are the proposal), notifications,
and which health data is collected. Each gets its own ADR when its phase is planned.

## Consequences

- ADR-0009 (owner-only bot) and ADR-0012 (dashboard sign-in through Telegram) stay binding
  until an ADR for invites and web sign-in supersedes them; until then the app keeps exactly one
  user.
- Each new surface (web sign-in, Web Push, a health-data endpoint, invites) updates
  `docs/security/threat-model.md` in the same PR, since each moves a trust boundary.
- Public use brings GDPR Art. 9 duties (explicit consent, DPIA, export and delete); they are
  designed in, and become blocking before anyone else's data is stored.
- Hosting on the Pi is fine for Liam and a few invited people; a public launch needs its own
  decision (cloud, cost, support).
