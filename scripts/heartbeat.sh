#!/usr/bin/env bash
# Tell the uptime monitor the app is up (ADR-0045). Started every 5 minutes by
# training-coach-heartbeat.timer; safe to run by hand.
#
# Healthchecks.io alerts Liam when the pings stop (the Pi, its power or its network is down) or
# when one reports a failure (the Pi is up but the app doesn't answer /healthz). The Pi only
# calls out: nothing new is reachable from outside.
#
# Settings come from $TC_HEARTBEAT_ENV (default ~/.config/training-coach/heartbeat.env, mode 600;
# whoever has the ping URL can fake pings):
#   TC_HEARTBEAT_URL   the check's ping URL (https://hc-ping.com/<uuid>)
# Env: TC_HEALTH_URL   default http://127.0.0.1:8095/healthz (the port on vybe-pi)
# Setup: docs/runbooks/deploy.md, "Uptime monitoring".
set -euo pipefail

ENV_FILE="${TC_HEARTBEAT_ENV:-$HOME/.config/training-coach/heartbeat.env}"
HEALTH_URL="${TC_HEALTH_URL:-http://127.0.0.1:8095/healthz}"

fail() { echo "heartbeat: ERROR: $*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || fail "no settings at $ENV_FILE (see the runbook)"
mode=$(stat -c '%a' "$ENV_FILE")
[ "$mode" = "600" ] || [ "$mode" = "400" ] || fail "$ENV_FILE must be mode 600 (it holds the ping URL), not $mode"
set -a
# shellcheck source=/dev/null
. "$ENV_FILE"
set +a
: "${TC_HEARTBEAT_URL:?set in $ENV_FILE}"
case "$TC_HEARTBEAT_URL" in
  https://*) ;;
  *) fail "TC_HEARTBEAT_URL must be an https:// URL" ;;
esac

# Not `curl | grep -q`: grep stopping early can fail the pipeline under pipefail.
body=$(curl -fsS --max-time 10 "$HEALTH_URL" 2>/dev/null) || body=""
if [[ "$body" == *'"status":"ok"'* ]]; then
  curl -fsS --max-time 10 --retry 3 -o /dev/null "$TC_HEARTBEAT_URL" || fail "the ping didn't go out"
else
  # Up but not answering: report it now instead of waiting out the check's grace period. The
  # body is the app's own health answer (no personal data), cut short.
  curl -fsS --max-time 10 --retry 3 -o /dev/null --data-raw "healthz: ${body:0:200}" \
    "$TC_HEARTBEAT_URL/fail" || fail "the failure ping didn't go out"
  echo "heartbeat: the app didn't answer /healthz; reported it"
fi
