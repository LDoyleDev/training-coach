# ADR-0009: Telegram via long polling, owner-only

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The bot is the main interface. Webhooks need a public HTTPS endpoint that accepts traffic from
Telegram; long polling makes outbound requests only.

## Decision

Use long polling. Nothing inbound is opened for the bot. Every handler is registered with a
filter for the single configured user ID (`TC_TELEGRAM_ALLOWED_USER_ID`); updates from anyone
else are dropped and logged at debug level without content.

## Consequences

- Phase 1 adds no attack surface to the Pi.
- A leaked bot token lets someone impersonate the bot but not read Liam's data; rotation is in
  `docs/runbooks/rotate-secrets.md`.
- A test asserts every registered handler carries the owner filter.
