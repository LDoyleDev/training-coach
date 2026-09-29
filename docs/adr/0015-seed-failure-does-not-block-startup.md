# ADR-0015: A failed plan seed does not block startup

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The container runs `alembic upgrade head`, then `training-coach seed`, then the app. If a
failing step stopped startup, a bad `plan.toml` would crash-loop the container on the Pi and
take the bot down, even though the database still holds a working plan.

## Decision

- A failed **migration** stops startup: code and schema would not match.
- A failed **seed** does not. `training-coach seed` logs `seed.failed` with the reason and
  exits 1; the start command continues and serves with the plan already in the database.
- The seed refuses, before any write, plans that would remove a session or shorten a ladder
  (history depends on them); those changes need a data migration. Items removed from a
  session are deleted, since nothing references them.
- CI validates the bundled `plan.toml`, so an invalid file should never reach `main`.

## Consequences

- On a brand-new database a failed seed leaves no plan. The bot must handle "no plan" by
  telling the user instead of crashing (step 1-D).
- After deploying a plan change, check `make logs` for `seed.applied` (deploy runbook).
