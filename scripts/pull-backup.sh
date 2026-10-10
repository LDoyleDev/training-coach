#!/usr/bin/env bash
# Copy the Pi's nightly database backups to this machine over Tailscale (ADR-0010).
# Run on the desktop (Linux or WSL), e.g. daily from cron:
#   15 9 * * * ~/training-coach/scripts/pull-backup.sh >> ~/backups/training-coach.log 2>&1
# Requires rsync, and SSH to the Pi as a user in its backup group (docs/runbooks/backup-restore.md).
# Usage: scripts/pull-backup.sh [destination]    (default: ~/backups/training-coach)
set -euo pipefail

PI="${TC_PI_HOST:-vybe@vybe-pi}"
SOURCE="${TC_PI_BACKUPS:-training-coach/data/backups/}"
DEST="${1:-$HOME/backups/training-coach}"

command -v rsync >/dev/null || { echo "rsync is required"; exit 1; }
mkdir -p "$DEST"
chmod 700 "$DEST" # the copies hold the same personal data as the live database

# Hidden files are backups still being written; skip them.
rsync -a --exclude='.*' -- "$PI:$SOURCE" "$DEST/"

# Retention (ADR-0042, ADR-0044): copies older than KEEP_DAYS go, nightly and manual alike, so
# data deleted or erased in the app is gone from every copy within that time.
KEEP_DAYS="${TC_DESKTOP_KEEP_DAYS:-35}"
find "$DEST" -maxdepth 1 -name 'training_coach-2*.db' -mtime "+$KEEP_DAYS" -delete
find "$DEST" -maxdepth 1 -name 'training_coach-manual-*.db' -mtime "+$KEEP_DAYS" -delete

# Liveness: a pull that works but brings nothing new means the Pi stopped backing up.
if [ -z "$(find "$DEST" -maxdepth 1 -name 'training_coach-2*.db' -mtime -2 -print -quit)" ]; then
  echo "WARNING: no nightly backup newer than 2 days in $DEST; check backup.failed on the Pi" >&2
  exit 1
fi
newest=$(find "$DEST" -maxdepth 1 -name 'training_coach-2*.db' | sort | tail -n 1)
echo "ok: newest nightly backup is $(basename "$newest")"
