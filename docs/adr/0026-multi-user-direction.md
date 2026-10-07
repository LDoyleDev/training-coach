# ADR-0026: Built for one, designed for many

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam

## Context

Phase 1 is built for one person: one allowed Telegram user (ADR-0009), one plan, no user ids in
the schema. Liam has decided the app should become available to other people in the end, used
from a web app and later a phone app as well as Telegram, starting on Android with iPhone kept
possible, and with no spending for now. Options and research: `docs/specs/platform-and-health-
data-proposal.md`.

## Decision

- **Telegram is one surface among several.** The web app gets everything the bot does; logic stays
  in `services/` and `domain/` (import-linter enforces it), so a new surface adds adapters only.
- **Multi-user ready from the next schema change.** A `users` table (Liam as the only row) and a
  `user_id` on every per-person table, with every query scoped by it and a test that enforces
  it. Single-user behaviour stays until invites exist.
- **Sign-in that doesn't need Telegram** (passkeys, with Telegram sign-in kept), designed in the
  web app phase; it extends ADR-0012.
- **Zero spend until decided otherwise:** no paid APIs, aggregators, store fees or subscriptions.
  Health data comes in through free, on-phone routes first (Android Health Connect).
- **Stays a fitness app:** no diagnoses or medical advice (EU Medical Device Regulation).

## Consequences

- ADR-0009 (owner-only bot) stays true for now and is superseded when invites ship.
- Public use brings GDPR Art. 9 duties (explicit consent, DPIA, export and delete); they are
  designed in, and become blocking before anyone else's data is stored.
- Hosting on the Pi is fine for Liam and a few invited people; a public launch needs its own
  decision (cloud, cost, support).
