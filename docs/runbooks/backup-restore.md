# Runbook: backup and restore

Backups are created nightly by the app into `data/backups/` (phase 1, step 1-H) and pulled to
the desktop with `scripts/pull-backup.sh` over Tailscale.

## Manual backup (before risky changes)

```bash
docker compose exec app python -c "import sqlite3; s=sqlite3.connect('/data/training_coach.db'); d=sqlite3.connect('/data/backups/manual.db'); s.backup(d)"
```

## Restore

```bash
make down
cp data/training_coach.db data/training_coach.db.broken
cp data/backups/<file>.db data/training_coach.db
rm -f data/training_coach.db-wal data/training_coach.db-shm
sudo chown 10001:10001 data/training_coach.db
make up
```

Rehearse a restore at least once per phase and note it in the release PR.
