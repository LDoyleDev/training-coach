#!/usr/bin/env bash
# Deploy the newest release tag on the Pi when there is one (ADR-0030).
# Run every 15 minutes by the training-coach-deploy timer (scripts/systemd/); safe to run by hand.
#   fetch tags -> already on the newest? exit quietly -> backup -> checkout tag -> rebuild ->
#   wait for /healthz to report the new version. If it never does, roll the code back, unless
#   the release changed the schema (then restoring the backup needs a person). Either way the
#   failed tag is not tried again until someone deploys by hand or deletes .git/auto-deploy-failed.
# Env: TC_DEPLOY_REMOTE    where tags come from (default: the public repo over HTTPS)
#      TC_HEALTH_URL       default http://127.0.0.1:8095/healthz (the port on vybe-pi)
#      TC_HEALTH_TIMEOUT   seconds to wait for health after a rebuild (default 180)
#      TC_HEALTH_INTERVAL  seconds between health checks (default 5)
set -euo pipefail

REPO_DIR="${TC_REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
REMOTE="${TC_DEPLOY_REMOTE:-https://github.com/LDoyleDev/training-coach.git}"
HEALTH_URL="${TC_HEALTH_URL:-http://127.0.0.1:8095/healthz}"
HEALTH_TIMEOUT="${TC_HEALTH_TIMEOUT:-180}"
HEALTH_INTERVAL="${TC_HEALTH_INTERVAL:-5}"
FAILED_MARK=".git/auto-deploy-failed"

log() { echo "auto-deploy: $*"; }

# True once /healthz returns the given JSON fragment.
healthy() {
  local body deadline=$((SECONDS + HEALTH_TIMEOUT))
  while :; do
    # Not `curl | grep -q`: grep stopping early can fail the pipeline under pipefail.
    body=$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null) || body=""
    if [[ "$body" == *"$1"* ]]; then
      return 0
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
      return 1
    fi
    sleep "$HEALTH_INTERVAL"
  done
}

main() {
  cd "$REPO_DIR"
  exec 9>.git/auto-deploy.lock
  if command -v flock >/dev/null && ! flock -n 9; then
    log "another deploy is running"
    return 0
  fi

  # Tags are fetched without +: a release tag that moved is refused, not deployed.
  git fetch --quiet --no-tags "$REMOTE" \
    "+refs/heads/main:refs/remotes/deploy/main" "refs/tags/v*:refs/tags/v*"
  local latest
  latest=$(git tag --list 'v*' --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -n 1) || true
  if [ -z "$latest" ]; then
    log "no release tags yet"
    return 0
  fi

  local current target
  current=$(git rev-parse HEAD)
  target=$(git rev-parse "$latest^{commit}")
  if [ "$current" = "$target" ]; then
    return 0 # the usual case: nothing to do, nothing to log
  fi
  if [ "$(cat "$FAILED_MARK" 2>/dev/null)" = "$latest" ]; then
    return 0 # already failed once; a person decides what happens next
  fi
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    log "ERROR: the checkout has local changes; not deploying $latest (deploy by hand)"
    return 1
  fi
  if ! git merge-base --is-ancestor "$target" refs/remotes/deploy/main; then
    log "ERROR: $latest is not on main; not deploying it"
    return 1
  fi
  if ! git merge-base --is-ancestor "$current" "$target"; then
    log "ERROR: the checkout ($(git describe --tags --always)) is not behind $latest; deploy by hand"
    return 1
  fi

  local from schema_changed=no
  from=$(git describe --tags --always)
  git diff --quiet "$current" "$target" -- backend/migrations || schema_changed=yes
  log "deploying $latest over $from"
  if ! docker compose exec -T app training-coach backup; then
    log "ERROR: the pre-deploy backup failed; not deploying $latest"
    return 1
  fi

  git -c advice.detachedHead=false checkout --quiet "$latest"
  if docker compose up -d --build && healthy "\"version\":\"${latest#v}\""; then
    rm -f "$FAILED_MARK"
    log "deployed $latest"
    return 0
  fi

  echo "$latest" >"$FAILED_MARK"
  log "ERROR: $latest did not report healthy within ${HEALTH_TIMEOUT}s"
  if [ "$schema_changed" = yes ]; then
    log "ERROR: $latest changed the schema, so going back means restoring the pre-deploy" \
      "backup; left as is for a person (docs/runbooks/deploy.md, Rollback)"
    return 1
  fi
  git -c advice.detachedHead=false checkout --quiet "$current"
  if docker compose up -d --build && healthy '"status":"ok"'; then
    log "rolled back to $from"
  else
    log "ERROR: rolled the code back to $from but it is not healthy either"
  fi
  return 1
}

# The checkout replaces this file; bash has read all of main() before it runs.
main "$@"
exit $?
