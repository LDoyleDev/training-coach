# ADR-0024: Backups run in the app, not the bot, and only a complete copy counts

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam

## Context

ADR-0010 sets nightly online backups with 7 daily and 4 weekly copies, pulled to the desktop.
It leaves open where the job runs, how retention counts, and how the desktop reads files the
container writes as uid 10001. The bot's JobQueue already schedules the morning message, but
the bot is off whenever its Telegram settings are missing, and a Telegram outage must not stop
backups.

## Decision

- The nightly backup is an asyncio task started by the app lifespan, independent of the bot.
  It runs at 03:30 Europe/Berlin (clear of the 02:00-03:00 DST jumps) and once on start if
  today has no backup, since the Pi may have been off at 03:30.
- A backup is written to a hidden `.partial` file, checked with `PRAGMA integrity_check`, and
  renamed into place. A file with the nightly name is always complete; a failure leaves the
  previous backups untouched, logs `backup.failed` and messages the owner when the bot is on.
- Retention counts the backups that exist, not calendar days: the newest 7, plus the newest of
  each of the 4 ISO weeks before them. Missed nights never cost a kept backup. Pruning only
  touches files with the nightly name; manual backups (`training-coach backup`) are kept.
- Backups are mode 0640 with the app's group (gid 10001). The desktop pull reads them as a
  host user added to that group, rather than making personal data world-readable or giving
  the pull passwordless sudo.

## Consequences

- One more long-running task in the process; it never raises (a dead loop would mean silent
  loss of backups), and it is cancelled cleanly on shutdown.
- A one-time host step on the Pi (group membership) before the first pull.
- `scripts/pull-backup.sh` warns and exits non-zero when nothing newer than two days arrives,
  so a working pull of stale backups is noticed.
