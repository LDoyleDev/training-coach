#!/usr/bin/env bash
# Read-only look at the live coach on the Pi, for a separate SSH key that may run nothing else
# (docs/runbooks/pi-read-access.md). Installed as ~/bin/tc-read and named in that key's
# authorized_keys line as its forced command, so whatever the client asks for arrives here in
# SSH_ORIGINAL_COMMAND and only the subcommands below run. Nothing here writes: the database is
# opened read-only, with query_only on and an authorizer that allows reads only.
#   status            version, container health, deploy timer, disk, memory, temperature
#   logs [SINCE] [TEXT]  app logs without health checks; SINCE like 30m, 6h, 2d (default 6h),
#                     TEXT a fixed string to keep (case-insensitive)
#   deploy            the last runs of the auto-deploy service
#   band              band import: last sync, last refusal, what has arrived
#   sql QUERY         one SELECT (or WITH, or a schema PRAGMA); at most 500 rows; secret columns
#                     (hashes, tokens, keys) come back empty
# The installed copy is not updated by deploys: changing what the key can do is a deliberate
# copy, not a side effect of a release.
set -euo pipefail
set -f # no globbing of anything the client sent

REPO_DIR="${TC_REPO_DIR:-$HOME/training-coach}"
DB_URI="file:/data/training_coach.db?mode=ro"

# Runs inside the app container. argv[1] is the query, passed as one argument: no shell sees it.
read -r -d '' QUERY_PY <<'PY' || true
import re, sqlite3, sys, time

SECRET = re.compile(r"hash|secret|token|credential|public_key|private|password|challenge|cookie", re.I)
PRAGMAS = {"table_info", "table_xinfo", "index_list", "index_info", "foreign_key_list"}
query = sys.argv[1].strip()
if not re.match(r"(select|with|pragma)\b", query, re.I):
    sys.exit("only SELECT, WITH or a schema PRAGMA")
db = sqlite3.connect(sys.argv[2], uri=True)
db.execute("PRAGMA query_only = ON")


def allow(action, arg1, arg2, _db, _source):
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_IGNORE if SECRET.search(arg2 or "") else sqlite3.SQLITE_OK
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, getattr(sqlite3, "SQLITE_RECURSIVE", 33)):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() in PRAGMAS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


db.set_authorizer(allow)
deadline = time.monotonic() + 20
db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
cursor = db.execute(query)
print("\t".join(c[0] for c in cursor.description or ()))
for row in cursor.fetchmany(500):
    print("\t".join("" if v is None else str(v) for v in row))
PY

query() {
  (cd "$REPO_DIR" && docker compose exec -T app python -c "$QUERY_PY" "$1" "$DB_URI")
}

usage() {
  sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2
  exit 2
}

read -r sub rest <<<"${SSH_ORIGINAL_COMMAND:-${*:-}}" || true
case "${sub:-}" in
  status)
    cd "$REPO_DIR"
    echo "now:      $(date -u '+%F %T UTC')"
    echo "version:  $(git describe --tags 2>/dev/null || echo unknown)"
    echo "app:      $(docker compose ps app --format '{{.Status}} since {{.CreatedAt}}')"
    echo "deploy:   $(systemctl list-timers training-coach-deploy.timer --no-pager --no-legend 2>/dev/null | head -1)"
    echo "uptime:  $(uptime)"
    df -h / | tail -1 | awk '{print "disk:     " $3 " used of " $2 " (" $5 ")"}'
    free -m | awk '/^Mem:/ {print "memory:   " $3 " MB used of " $2 " MB"}'
    command -v vcgencmd >/dev/null && echo "temp:     $(vcgencmd measure_temp)" || true
    ;;
  logs)
    read -r since text <<<"${rest:-}" || true
    since="${since:-6h}"
    [[ "$since" =~ ^[0-9]{1,4}[smhd]$ ]] || { echo "SINCE like 30m, 6h or 2d" >&2; exit 2; }
    cd "$REPO_DIR"
    if [[ -n "${text:-}" ]]; then
      docker compose logs --no-color --since "$since" app 2>&1 | grep -v healthz | grep -iF -- "$text" | tail -n 300
    else
      docker compose logs --no-color --since "$since" app 2>&1 | grep -v healthz | tail -n 300
    fi
    ;;
  deploy)
    journalctl -u training-coach-deploy.service -n 60 --no-pager 2>&1 || true
    ;;
  band)
    query "SELECT created_at, last_used_at, last_taken_at, alerted_at FROM ingest_keys"
    echo
    query "SELECT feed, last_taken_at, alerted_at FROM band_feeds"
    echo
    query "SELECT 'health_days', count(*), max(local_date) FROM health_days
           UNION ALL SELECT 'sleep_sessions', count(*), max(local_date) FROM sleep_sessions
           UNION ALL SELECT 'imported_workouts', count(*), max(local_date) FROM imported_workouts
           UNION ALL SELECT 'heart_rate_samples', count(*), max(at) FROM heart_rate_samples"
    ;;
  sql)
    [[ -n "${rest:-}" ]] || usage
    query "$rest"
    ;;
  *)
    usage
    ;;
esac
