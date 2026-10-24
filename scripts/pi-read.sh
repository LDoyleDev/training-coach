#!/usr/bin/env bash
# Read-only look at the live coach on the Pi, for a separate SSH key that may run nothing else
# (docs/runbooks/pi-read-access.md). Installed as ~/bin/tc-read and named in that key's
# authorized_keys line as its forced command, so whatever the client asks for arrives here in
# SSH_ORIGINAL_COMMAND and only the subcommands below run. Nothing here writes: the database is
# opened read-only, with query_only on and an authorizer that allows reads only.
#   status            version, container health, deploy timer, disk, memory, temperature
#   logs [SINCE] [TEXT]  app logs without health checks, known secret shapes redacted; SINCE like 30m, 6h, 2d (default 6h),
#                     TEXT a fixed string to keep (case-insensitive)
#   deploy            the last runs of the auto-deploy service
#   band              band import: last sync, last refusal, what has arrived
#   sql QUERY         one SELECT (or WITH, or a schema PRAGMA); at most 500 rows, 100 columns and
#                     4 MB back, 64 MB of memory and 20 s to run; secret columns (hashes, tokens,
#                     keys, photos) come back empty
# The installed copy is not updated by deploys: changing what the key can do is a deliberate
# copy, not a side effect of a release.
set -euo pipefail
set -f # no globbing of anything the client sent

REPO_DIR="${TC_REPO_DIR:-$HOME/training-coach}"
DB_URI="file:/data/training_coach.db?mode=ro"

# Runs inside the app container. argv[1] is the query, passed as one argument: no shell sees it.
read -r -d '' QUERY_PY <<'PY' || true
import itertools, re, sqlite3, sys, time

try:
    import resource
except ImportError:  # Windows, where the tests also run this; the Pi is Linux
    resource = None

# Kept in step with the models by tests/test_pi_read.py: every secret or binary column matches.
SECRET = re.compile(r"hash|secret|token|key|credential|private|password|challenge|cookie|jpeg|photo|image", re.I)
PRAGMAS = {"table_info", "table_xinfo", "index_list", "index_info", "foreign_key_list"}
# Only these functions: nothing that loads code or builds a huge value in one call (zeroblob).
FUNCTIONS = {
    "abs", "avg", "coalesce", "count", "date", "datetime", "group_concat", "ifnull", "iif",
    "instr", "json_array_length", "json_extract", "julianday", "length", "lower", "max", "min",
    "nullif", "printf", "replace", "round", "strftime", "substr", "substring", "sum", "time",
    "total", "trim", "typeof", "unixepoch", "upper",
}
# The query runs in the app's container and counts against its 512 MB (compose.yaml). Had it used
# that up, the kernel would kill the app, the biggest process there, so the query has a budget
# of its own and fails first (review of 2026-10-24): SQLite's heap is capped, sorts and temporary
# tables stay in that heap instead of spilling to /tmp (a tmpfs, counted against the same 512 MB),
# and the whole process is held to a small address space. The output is capped in total too.
HEAP_MB, PROCESS_MB, OUTPUT_MB, MAX_COLUMNS, MAX_ROWS = 64, 192, 4, 100, 500
if resource is not None:
    resource.setrlimit(resource.RLIMIT_AS, (PROCESS_MB << 20, PROCESS_MB << 20))
query = sys.argv[1].strip()
if not re.match(r"(select|with|pragma)\b", query, re.I):
    sys.exit("only SELECT, WITH or a schema PRAGMA")
db = sqlite3.connect(sys.argv[2], uri=True)
db.execute("PRAGMA query_only = ON")
db.execute("PRAGMA temp_store = MEMORY")
db.execute(f"PRAGMA hard_heap_limit = {HEAP_MB << 20}")
budget = (db.execute("PRAGMA temp_store").fetchone(), db.execute("PRAGMA hard_heap_limit").fetchone())
if budget != ((2,), (HEAP_MB << 20,)):
    sys.exit("this SQLite can't hold the query to a memory budget, so it doesn't run")


def allow(action, arg1, arg2, _db, _source):
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_IGNORE if SECRET.search(arg2 or "") else sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_OK if (arg2 or "").lower() in FUNCTIONS else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_SELECT, getattr(sqlite3, "SQLITE_RECURSIVE", 33)):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() in PRAGMAS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


db.set_authorizer(allow)
db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)  # no value over 1 MB
db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, MAX_COLUMNS)  # the widest table has 20
deadline = time.monotonic() + 20
db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)


def run():
    cursor = db.execute(query)
    header = "\t".join(c[0] for c in cursor.description or ())
    print(header)
    size = len(header) + 1
    for row in itertools.islice(cursor, MAX_ROWS):  # one row at a time, not all 500 at once
        values = ["" if v is None else str(v) for v in row]
        size += sum(map(len, values)) + len(values)
        if size > OUTPUT_MB * 1_000_000:
            sys.exit(f"stopped at {OUTPUT_MB} MB of output: ask for fewer or narrower columns, or fewer rows")
        print("\t".join(values))


try:
    run()
except MemoryError:
    sys.exit(f"the query needs more than its {HEAP_MB} MB of memory: add a LIMIT (a sort then keeps only those rows), or ask for fewer or narrower columns")
except sqlite3.Error as error:
    sys.exit("stopped at the 20 s limit" if time.monotonic() > deadline else f"failed: {error}")
PY

query() {
  (cd "$REPO_DIR" && docker compose exec -T app python -c "$QUERY_PY" "$1" "$DB_URI")
}

usage() {
  sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2
  exit 2
}

command="${SSH_ORIGINAL_COMMAND:-${*:-}}"
command="${command#"${command%%[![:space:]]*}"}" # leading spaces off
sub="${command%%[[:space:]]*}"
rest="${command#"$sub"}" # everything after the subcommand, newlines kept (a multi-line query)
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
    # Not masked like the database: the app's logging rules keep secrets out (backend/CLAUDE.md),
    # and these known shapes are redacted on top: query strings, bot tokens in Telegram URLs,
    # bearer headers and ingest secrets.
    redact() {
      sed -E -e 's#\?[^ "]*#?...#g' -e 's#bot[0-9]+:[A-Za-z0-9_-]+#bot<redacted>#g' \
        -e 's#([Bb]earer) [^ "]+#\1 <redacted>#g' -e 's#tci_[A-Za-z0-9_-]+#tci_<redacted>#g'
    }
    read -r since text <<<"${rest:-}" || true
    since="${since:-6h}"
    [[ "$since" =~ ^[0-9]{1,4}[smhd]$ ]] || { echo "SINCE like 30m, 6h or 2d" >&2; exit 2; }
    cd "$REPO_DIR"
    # grep finding nothing is an answer, not a failure: under pipefail it ended the script, silent.
    # An empty TEXT keeps every line.
    lines="$(docker compose logs --no-color --since "$since" app 2>&1 | { grep -v healthz || true; } |
      redact | { grep -iF -- "${text:-}" || true; } | tail -n 300)"
    if [[ -n "$lines" ]]; then
      printf '%s\n' "$lines"
    else
      echo "no matching lines in the last $since"
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
