# ADR-0010: SQLite on the SD card, with nightly backups

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The Pi boots from an SD card and runs continuously. SD cards wear with writes and can corrupt
on power loss. Data volume is tiny (a few rows a day).

## Decision

SQLite with WAL mode and `synchronous=NORMAL`, writes batched per user action. A nightly
online backup (SQLite backup API) to `data/backups/`, rotated (7 daily, 4 weekly), and copied
to the desktop over Tailscale. Restores are rehearsed (runbook).

## Consequences

- Maximum data loss: one day.
- Moving the Pi to NVMe is recommended but not required; revisit if corruption ever occurs.
