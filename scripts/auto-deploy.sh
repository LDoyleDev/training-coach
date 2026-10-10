#!/usr/bin/env bash
# Deploy the newest release tag on the Pi when there is one (ADR-0030).
# Run every 15 minutes by the training-coach-deploy timer (scripts/systemd/); safe to run by hand.
#   fetch tags -> already on the newest? exit quietly -> on main and signed by GitHub? ->
#   backup -> checkout tag -> rebuild ->
#   wait for /healthz to report the new version. If it never does, roll the code back, unless
#   the release changed the schema (then restoring the backup needs a person). Either way the
#   failed tag is not tried again until someone deploys by hand or deletes .git/auto-deploy-failed.
# Env: TC_DEPLOY_REMOTE    where tags come from (default: the public repo over HTTPS)
#      TC_HEALTH_URL       default http://127.0.0.1:8095/healthz (the port on vybe-pi)
#      TC_HEALTH_TIMEOUT   seconds to wait for health after a rebuild (default 180)
#      TC_HEALTH_INTERVAL  seconds between health checks (default 5)
#      TC_DEPLOY_GPG       the gpg that checks a release is GitHub's (default: gpg)
set -euo pipefail

REPO_DIR="${TC_REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
REMOTE="${TC_DEPLOY_REMOTE:-https://github.com/LDoyleDev/training-coach.git}"
HEALTH_URL="${TC_HEALTH_URL:-http://127.0.0.1:8095/healthz}"
HEALTH_TIMEOUT="${TC_HEALTH_TIMEOUT:-180}"
HEALTH_INTERVAL="${TC_HEALTH_INTERVAL:-5}"
GPG="${TC_DEPLOY_GPG:-gpg}"
FAILED_MARK=".git/auto-deploy-failed"
# GitHub signs every commit it makes, squash merges included, with this key (ADR-0043). Pinned
# here and read from the checkout already deployed, so a release can't vouch for itself.
GITHUB_KEY="scripts/keys/github-web-flow.gpg"
GITHUB_FINGERPRINT="968479A1AFF927E37D1A566BB5690EEEBB952194"

log() { echo "auto-deploy: $*"; }

# True if the commit carries a good signature by GitHub's key: GitHub made it (a merge, or a
# commit through its web editor or API), so it wasn't a plain `git push` (ADR-0043).
signed_by_github() {
  local home status primary=""
  home=$(mktemp -d)
  if "$GPG" --homedir "$home" --batch --quiet --import "$GITHUB_KEY" 2>/dev/null; then
    # verify-commit prints gpg's status lines on stderr; it fails on no or a bad signature.
    status=$(GNUPGHOME="$home" git -c gpg.program="$GPG" verify-commit --raw "$1" 2>&1) || status=""
    # VALIDSIG's last field is the primary key's fingerprint; GOODSIG means not expired or revoked.
    if [[ "$status" == *"[GNUPG:] GOODSIG "* ]]; then
      primary=$(echo "$status" | awk '$2 == "VALIDSIG" { print $NF }')
    fi
  fi
  command -v gpgconf >/dev/null && gpgconf --homedir "$home" --kill all 2>/dev/null
  rm -rf "$home"
  [ "$primary" = "$GITHUB_FINGERPRINT" ]
}

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

  # Tags are fetched without +: a release tag that moved is refused, not deployed. That stops
  # every deploy until a person looks, which is the point: release tags never move.
  if ! git fetch --quiet --no-tags "$REMOTE" \
    "+refs/heads/main:refs/remotes/deploy/main" "refs/tags/v*:refs/tags/v*"; then
    log "ERROR: fetching releases failed (network down, or a release tag moved upstream)"
    return 1
  fi
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
  if ! command -v "$GPG" >/dev/null; then
    log "ERROR: gpg is needed to check $latest is genuine (sudo apt install gnupg)"
    return 1
  fi
  if ! signed_by_github "$target"; then
    log "ERROR: $latest is not signed by GitHub, so it wasn't merged there; not deploying it"
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
  # In the running app if it is up; otherwise in a one-off container of the current image, so
  # a release that fixes a crashing app can still go out.
  if ! docker compose exec -T app training-coach backup &&
    ! docker compose run --rm --no-deps -T app training-coach backup; then
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
  # Back on a release, wait for its version, so a container left over from the bad build can't
  # pass for it. A checkout that isn't on a release has no version to wait for.
  local previous='"status":"ok"'
  if [[ "$from" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    previous="\"version\":\"${from#v}\""
  fi
  git -c advice.detachedHead=false checkout --quiet "$current"
  if docker compose up -d --build && healthy "$previous"; then
    log "rolled back to $from"
  else
    log "ERROR: rolled the code back to $from but it is not healthy either"
  fi
  return 1
}

# The checkout replaces this file; bash has read all of main() before it runs.
main "$@"
exit $?
