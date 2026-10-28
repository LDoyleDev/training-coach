# ADR-0081: SQLite savepoints open the transaction first

- Status: Proposed
- Date: 2026-10-28
- Deciders: Liam

## Context

Python's `sqlite3` (legacy transaction control, its default; SQLAlchemy's docs expect that to
change in Python 3.16) opens a transaction only at an INSERT, UPDATE or DELETE, not at a SELECT
or a SAVEPOINT. When a session's first write was inside `begin_nested()`, the SAVEPOINT stood
alone: SQLite treats an outermost savepoint as the transaction, so releasing it committed its
rows, and a later rollback left them in. Found while fixing #413 (ADR-0080), where
`session_levels.change` was written around it; a test now shows it.

Ten places use `begin_nested()`, most for races (a double tap, web and bot at once). Migrations
already take transactions out of the driver's hands in `migrations/env.py`, so their DDL is
inside one transaction.

## Decision

`make_engine` listens for SQLAlchemy's `savepoint` event: if the driver has no transaction
open yet, it emits `BEGIN` before the SAVEPOINT. Nothing else changes: reads before the first
write still run outside a transaction, and writes still open one at the first INSERT, UPDATE
or DELETE.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| BEGIN before a savepoint only (chosen) | Fixes the savepoint; locking stays as it was; one small hook | Reads before a write are still outside the transaction (as before) |
| SQLAlchemy's pysqlite recipe for every session (driver `isolation_level=None`, BEGIN on every transaction) | Standard; every read inside its transaction | Each session's reads take a WAL snapshot, so a read-then-write that races another connection's write fails "database is locked" instead of waiting; the fitness test race (`test_a_save_racing_another_with_the_same_token_returns_the_saved_day`) fails with it |
| The same recipe with `BEGIN IMMEDIATE` | No stale snapshots | Every session, reads too, takes the write lock; a session waiting on it blocks the bot's event loop up to 5 s; the race tests' interleaving can't run in one thread |
| `connect_args={"autocommit": False}` (Python 3.12) | PEP 249 transactions | A transaction is always open, so the connect pragmas would run inside one: `foreign_keys=ON` does nothing there and WAL is refused (checked on 3.12) |

## Consequences

- A row written first inside a savepoint is rolled back with its session, so a refused
  `change()` now also undoes the progress it started.
- `tests/db/test_session.py` covers a savepoint opened first, after reads, and inside a write.
- If Python changes the `sqlite3` default (3.16, per SQLAlchemy's docs), revisit this hook and
  `env.py`.
