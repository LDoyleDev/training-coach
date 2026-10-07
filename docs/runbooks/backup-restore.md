# Runbook: backup and restore

The app backs up its SQLite database every night at 03:30 (Europe/Berlin) into
`data/backups/`, and once on start if today has no backup yet (ADR-0010, step 1-H). Each
backup is a complete, standalone `.db` file: it is copied with SQLite's online backup API,
checked with `PRAGMA integrity_check`, and only then renamed into place.

| What | Where | Kept |
| --- | --- | --- |
| Nightly | `data/backups/training_coach-YYYY-MM-DD.db` | newest 7, plus the newest of each of the 4 weeks before them |
| Manual | `data/backups/training_coach-manual-<UTC time>.db` | until you delete it |
| Desktop copy | `~/backups/training-coach/` via `scripts/pull-backup.sh` | everything, never pruned |

A failed backup logs `backup.failed` and, when the bot is on, sends you a Telegram message.
Data loss is at most one day.

## Manual backup (before a deploy with a migration, or any risky change)

```bash
docker compose exec app training-coach backup    # logs backup.created with the file name
```

## Pulling backups to the desktop

One-time setup on the Pi, so your SSH user can read the backups (the app writes them as
uid/gid 10001, mode 0640):

```bash
getent group 10001          # must print nothing, or coach-data from an earlier run
sudo groupadd --gid 10001 coach-data       # the container's app group, by number
sudo usermod -aG coach-data vybe           # log out and back in afterwards
sudo chmod 750 data && sudo chmod 640 data/training_coach.db*   # not readable by other users
```

If gid 10001 already belongs to another group, stop: every member of that group could read
your data. Pick the fix with that group's owner first.

The app runs with umask 027, so database files it creates from now on are group-readable at
most; the `chmod` fixes ones created before.

Then on the desktop (Linux or WSL), run it once by hand and add the cron line from the
script's header:

```bash
scripts/pull-backup.sh            # ok: newest nightly backup is training_coach-2026-10-07.db
```

It exits non-zero with a warning when nothing newer than two days has arrived: the pull worked
but the Pi stopped backing up.

## Restore

```bash
make down                                                  # or: docker compose down
cp data/training_coach.db data/training_coach.db.broken    # keep the bad one for later
cp data/backups/<file>.db data/training_coach.db           # or copy one back from the desktop
rm -f data/training_coach.db-wal data/training_coach.db-shm
sudo chown 10001:10001 data/training_coach.db
make up                                                    # migrations run on start
curl -s localhost:8095/healthz && docker compose logs app | grep -E "bot.started|backup"
```

Restoring an older backup into a newer release is fine: migrations bring it up to date on
start. Restoring into an older release than the backup's needs that release's schema; check
out the matching tag first.

## Rehearsal

Rehearse a restore once per phase and note it in the release PR:

1. Take a manual backup (above) and note the row counts: `sqlite3 data/backups/<file>.db
   "select count(*) from workouts; select count(*) from set_logs;"`.
2. Restore it as above.
3. Check `/today` in the bot and the counts again.

Last rehearsed: 2026-10-07 on the desktop (#14): a seeded database with one logged workout was
backed up with `training-coach backup`, replaced with garbage (start-up then logs `seed.failed`),
and restored with the commands above. Migrations had nothing to do, the seed was unchanged, and
every row count and `PRAGMA integrity_check` matched. Still to do once on the Pi itself.
