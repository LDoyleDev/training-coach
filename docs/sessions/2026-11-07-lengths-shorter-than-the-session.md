# Session log: 7 Nov 2026 (1.18.1): lengths shorter than the session

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-07-plans-per-person.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.18.1 | #586 Short on time today offers only lengths shorter than the session due, and HIIT's estimate counts 30 s a round; #587 the 1.18.0 wrap. |

No migration and no data change. Released ahead of the change notices (#582), so this fix doesn't
wait for that migration's OK. Live at 08:45:36 CET; the Pi's head stays `b4e8d1f6a9c2`. Tested by
the suites, not yet seen on a real HIIT day.

## Decisions and where they live

- **Only lengths shorter than the session (Liam, 7 Nov):** ADR-0082 addendum.

## Open items and next steps

As in `2026-11-07-plans-per-person.md`, plus:

- **The starting starters and rest days:** draft PR #588, for Liam's review.
