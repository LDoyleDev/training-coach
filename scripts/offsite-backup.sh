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
#   TC_OFFSITE_PING_URL       optional: a Healthchecks.io check's ping URL; pinged after each
#                             good run and on a failure, so a job that stops running is noticed
#                             (the restore drill of 2026-10-25 found it had never run)
# Setup and restore: docs/runbooks/backup-restore.md, "Off-site copies".
set -euo pipefail

ENV_FILE="${TC_OFFSITE_ENV:-$HOME/.config/training-coach/offsite.env}"
BACKUPS="${TC_BACKUPS_DIR:-$HOME/training-coach/data/backups}"
KEEP_DAYS="${TC_OFFSITE_KEEP_DAYS:-35}"

log() { echo "offsite-backup: $*"; }
# Best effort: a ping that can't go out never hides the job's own result.
ping() {
  [ -n "${TC_OFFSITE_PING_URL:-}" ] || return 0
  curl -fsS --max-time 10 --retry 3 -o /dev/null "$TC_OFFSITE_PING_URL$1" ||
    echo "offsite-backup: WARNING: the ping to the monitor didn't go out" >&2
}
pinged=""
fail() {
  echo "offsite-backup: ERROR: $*" >&2
  ping /fail
  pinged=1
  exit 1
}
work=""
# Any other failure (age, rclone under set -e) reports too, once (review of #338).
on_exit() {
  local status=$?
  [ -z "$work" ] || rm -rf "$work"
  if [ "$status" -ne 0 ] && [ -z "$pinged" ]; then ping /fail; fi
}
trap on_exit EXIT

[ -f "$ENV_FILE" ] || fail "no settings at $ENV_FILE (see the runbook)"
mode=$(stat -c '%a' "$ENV_FILE")
[ "$mode" = "600" ] || [ "$mode" = "400" ] || fail "$ENV_FILE must be mode 600 (it holds the bucket token), not $mode"
set -a
# shellcheck source=/dev/null
. "$ENV_FILE"
set +a
case "${TC_OFFSITE_PING_URL:-}" in
  "") log "WARNING: no TC_OFFSITE_PING_URL: nobody is told if this job stops running" ;;
  https://*) ;;
  *) TC_OFFSITE_PING_URL="" && fail "TC_OFFSITE_PING_URL must be an https:// URL" ;;
esac
: "${TC_BACKUP_AGE_RECIPIENT:?set in $ENV_FILE}"
: "${TC_OFFSITE_BUCKET:?set in $ENV_FILE}"
recipients=()
set -f # split on spaces only: a stray * must not match files
for key in $TC_BACKUP_AGE_RECIPIENT; do
  case "$key" in age1*) recipients+=(-r "$key") ;; *) fail "TC_BACKUP_AGE_RECIPIENT has something that isn't an age public key" ;; esac
done
set +f
[ "${#recipients[@]}" -gt 0 ] || fail "TC_BACKUP_AGE_RECIPIENT lists no age public key"
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
  age "${recipients[@]}" -o "$work/$name" "$newest"
  # --s3-no-head: R2 answers 501 to the HEAD by version id that rclone 1.60 makes after each
  # upload, so every run needed a retry (26 Oct); the lsf below checks the upload instead.
  rclone copyto --s3-no-check-bucket --s3-no-head "$work/$name" "$remote/$name"
  rclone lsf "$remote/" --include "$name" | grep -qx "$name" || fail "upload of $name not found afterwards"
  log "uploaded $name"
fi

# Retention: nothing off-site is older than KEEP_DAYS.
rclone delete --min-age "${KEEP_DAYS}d" --include 'training_coach-*.db.age' "$remote/"
log "ok: kept the last $KEEP_DAYS days off-site"
ping ""
