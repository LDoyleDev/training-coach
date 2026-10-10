#!/usr/bin/env bash
# Encrypt the newest nightly backup and copy it off the Pi (ADR-0042). Started by
# training-coach-offsite.timer after the 03:30 backup; safe to run by hand any time.
#
# The backup is encrypted with age to the desktop's PUBLIC key, so the Pi can't read its own
# off-site copies and a leaked bucket token exposes nothing readable. Copies older than
# TC_OFFSITE_KEEP_DAYS are deleted, so deleted data really leaves backups within that time.
#
# Settings come from $TC_OFFSITE_ENV (default ~/.config/training-coach/offsite.env, mode 600):
#   TC_BACKUP_AGE_RECIPIENT   the backup keys' public halves (age1...), separated by spaces:
#                             any one of their private keys can decrypt, so a lost key
#                             doesn't lose the backups
#   TC_OFFSITE_BUCKET         the R2 bucket name
#   RCLONE_CONFIG_R2_TYPE=s3, RCLONE_CONFIG_R2_PROVIDER=Cloudflare,
#   RCLONE_CONFIG_R2_ACCESS_KEY_ID, RCLONE_CONFIG_R2_SECRET_ACCESS_KEY,
#   RCLONE_CONFIG_R2_ENDPOINT   (https://<account id>.r2.cloudflarestorage.com)
# Setup and restore: docs/runbooks/backup-restore.md, "Off-site copies".
set -euo pipefail

ENV_FILE="${TC_OFFSITE_ENV:-$HOME/.config/training-coach/offsite.env}"
BACKUPS="${TC_BACKUPS_DIR:-$HOME/training-coach/data/backups}"
KEEP_DAYS="${TC_OFFSITE_KEEP_DAYS:-35}"

log() { echo "offsite-backup: $*"; }
fail() { echo "offsite-backup: ERROR: $*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || fail "no settings at $ENV_FILE (see the runbook)"
mode=$(stat -c '%a' "$ENV_FILE")
[ "$mode" = "600" ] || [ "$mode" = "400" ] || fail "$ENV_FILE must be mode 600 (it holds the bucket token), not $mode"
set -a
# shellcheck source=/dev/null
. "$ENV_FILE"
set +a
: "${TC_BACKUP_AGE_RECIPIENT:?set in $ENV_FILE}"
: "${TC_OFFSITE_BUCKET:?set in $ENV_FILE}"
recipients=()
for key in $TC_BACKUP_AGE_RECIPIENT; do
  case "$key" in age1*) recipients+=(-r "$key") ;; *) fail "TC_BACKUP_AGE_RECIPIENT has something that isn't an age public key" ;; esac
done
command -v age >/dev/null || fail "age isn't installed (sudo apt install age)"
command -v rclone >/dev/null || fail "rclone isn't installed (sudo apt install rclone)"

# The newest nightly backup, which must be recent: an old one means backups stopped.
newest=$(find "$BACKUPS" -maxdepth 1 -name 'training_coach-2*.db' -mtime -2 | sort | tail -n 1)
[ -n "$newest" ] || fail "no nightly backup newer than 2 days in $BACKUPS; check backup.failed"
name="$(basename "$newest").age"
remote="r2:$TC_OFFSITE_BUCKET"

if rclone lsf "$remote/" --include "$name" | grep -qx "$name"; then
  log "$name is already off-site"
else
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
  age "${recipients[@]}" -o "$work/$name" "$newest"
  rclone copyto --s3-no-check-bucket "$work/$name" "$remote/$name"
  rclone lsf "$remote/" --include "$name" | grep -qx "$name" || fail "upload of $name not found afterwards"
  log "uploaded $name"
fi

# Retention: nothing off-site is older than KEEP_DAYS.
rclone delete --min-age "${KEEP_DAYS}d" --include 'training_coach-*.db.age' "$remote/"
log "ok: kept the last $KEEP_DAYS days off-site"
