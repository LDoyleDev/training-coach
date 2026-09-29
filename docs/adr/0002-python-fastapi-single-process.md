# ADR-0002: Python + FastAPI, one process for API and bot

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

One user, one Raspberry Pi 5 (8 GB) that already runs other services (Vybe). The backend must
run the Telegram bot, a scheduler (morning messages), the dashboard API and later an MCP
endpoint. Liam's other projects use Python and FastAPI.

## Decision

Python 3.12 with FastAPI, python-telegram-bot (with its APScheduler-based JobQueue) and
SQLAlchemy 2. A single process: FastAPI's lifespan starts and stops the bot. SQLite for storage
(see ADR-0010).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| One process, API + bot (chosen) | One container, lowest RAM, one place for scheduling, no cross-process DB locking | API restart restarts the bot (seconds of downtime, acceptable) |
| Separate API and bot processes | Independent restarts | Two containers, SQLite writer contention, more to operate |
| Node/TypeScript backend | Same language as frontend | Breaks from Liam's existing Python stack and tooling |

## Consequences

- Scheduling lives in the bot's JobQueue; jobs are rebuilt from the database on start.
- If the bot or scheduler ever needs independent scaling, revisit with a new ADR.
