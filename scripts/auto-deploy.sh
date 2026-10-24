#!/usr/bin/env bash
# Deploy the newest release tag on the Pi when there is one (ADR-0030).
# Run every 15 minutes by the training-coach-deploy timer (scripts/systemd/); safe to run by hand.
#   fetch tags -> already on the newest? exit quietly -> on main and signed by GitHub? ->
#   backup -> checkout tag -> rebuild ->
#   wait for /healthz to report the new version, then remove this app's older images. If it
#   never does, roll the code back, unless the release changed the schema (then restoring the
#   backup needs a person). Either way the failed tag is not tried again until someone deploys
#   by hand or deletes .git/auto-deploy-failed. A deploy cut off part way (a power cut, a
#   reboot, the unit's timeout) is finished by the next run (.git/auto-deploy-pending), after
#   the same checks again. A tag deployed here before is never deployed at another commit.
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
# "<tag> <commit deployed before> [resumed]": written before the checkout, removed once the
# deploy is over either way, so a run that finds it knows the last one was cut off.
PENDING_MARK=".git/auto-deploy-pending"
# "<tag> <commit>" for every tag deployed here, one line each, added after each healthy deploy:
# a tag deleted upstream and made again elsewhere isn't refused by the fetch, so by this.
DEPLOYED_TAGS=".git/auto-deploy-tags"
# The image that ran before the deploy in progress, written with the pending mark: the one the
# clean-up keeps for going back by hand.
REPLACED_IMAGE=".git/auto-deploy-replaced-image"
RELEASE='^v[0-9]+\.[0-9]+\.[0-9]+$'
IMAGE="training-coach:local"     # compose.yaml's image:
IMAGE_LABEL="training-coach.app" # the Dockerfile's LABEL: only these images are ever removed
# GitHub signs every commit it makes, squash merges included, with this key (ADR-0043). Pinned
# here and read from the commit already deployed, so a release can't vouch for itself.
GITHUB_KEY="scripts/keys/github-web-flow.gpg"
GITHUB_FINGERPRINT="968479A1AFF927E37D1A566BB5690EEEBB952194"

log() { echo "auto-deploy: $*"; }

# The first commit after $1 up to $2 without a good signature by GitHub's key; nothing if they
# all have one. GitHub signs what it makes (a merge, or a commit through its web editor or API),
# so a plain `git push` shows up here (ADR-0043). Every commit, not only the release's: one
# pushed earlier would otherwise ship under a release signed on top of it. Fails closed: if
# the commits can't be listed, or there are none, or the key won't load, it names $2.
unsigned_commit() {
  local home commits commit status primary found=""
  if ! commits=$(git rev-list --reverse "$1..$2" 2>/dev/null) || [ -z "$commits" ]; then
    echo "$2"
    return
  fi
  home=$(mktemp -d)
  # From $1, not the working tree: a resumed deploy may have the release checked out already.
  if ! git show "$1:$GITHUB_KEY" >"$home/github.gpg" 2>/dev/null ||
    ! "$GPG" --homedir "$home" --batch --quiet --import "$home/github.gpg" 2>/dev/null; then
    found="$2" # the key didn't load, so nothing is checked
  else
    for commit in $commits; do
      primary=""
      # verify-commit prints gpg's status lines on stderr; it fails on no or a bad signature.
      status=$(GNUPGHOME="$home" git -c gpg.program="$GPG" verify-commit --raw "$commit" 2>&1) ||
        status=""
      # VALIDSIG's last field is the primary key's fingerprint; GOODSIG: not expired or revoked.
      if [[ "$status" == *"[GNUPG:] GOODSIG "* ]]; then
        primary=$(echo "$status" | awk '$2 == "VALIDSIG" { print $NF }')
      fi
      if [ "$primary" != "$GITHUB_FINGERPRINT" ]; then
        found="$commit"
        break
      fi
    done
  fi
  if command -v gpgconf >/dev/null; then
    gpgconf --homedir "$home" --kill all 2>/dev/null || true
  fi
  rm -rf "$home"
  echo "$found"
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

# The image of the app's running container, or nothing.
running_image() {
  local container
  container=$(docker compose ps --quiet app 2>/dev/null | head -n 1) || container=""
  if [ -n "$container" ]; then
    docker inspect --format '{{.Image}}' "$container" 2>/dev/null || true
  fi
}

# After a healthy deploy: this app's images except the one running and the one that ran before
# the deploy ($REPLACED_IMAGE), kept for going back by hand. Not the newest other: after a
# rollback by hand whose build was all cached, the newest other never ran. If what ran before
# isn't known, nothing is removed. Never other projects' images, never volumes. Nothing here
# fails the deploy.
remove_old_images() {
  local running replaced ids id
  running=$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null) || return 0
  replaced=$(cat "$REPLACED_IMAGE" 2>/dev/null) || replaced=""
  if [ -z "$replaced" ]; then
    log "not removing old images: which one ran before this deploy isn't known"
    return 0
  fi
  # One line per tag: an image tagged twice is seen once.
  ids=$(docker image ls --quiet --no-trunc --filter "label=$IMAGE_LABEL" | awk '!seen[$0]++') ||
    return 0
  for id in $ids; do
    if [ "$id" != "$running" ] && [ "$id" != "$replaced" ] &&
      ! docker image rm "$id" >/dev/null 2>&1; then
      log "could not remove the old image $id (a container still uses it?)"
    fi
  done
}

# Rebuild on tag $1, checked out, and wait for its version. $2 is the commit deployed before.
finish_deploy() {
  local deployed
  if docker compose up -d --build && healthy "\"version\":\"${1#v}\""; then
    deployed="$1 $(git rev-parse HEAD)"
    if ! grep -qxF -- "$deployed" "$DEPLOYED_TAGS" 2>/dev/null; then
      { echo "$deployed" >>"$DEPLOYED_TAGS"; } 2>/dev/null ||
        log "could not write $DEPLOYED_TAGS (disk full?); $1 is deployed but not remembered"
    fi
    rm -f "$FAILED_MARK" "$PENDING_MARK"
    log "deployed $1"
    remove_old_images
    rm -f "$REPLACED_IMAGE"
    return 0
  fi
  log "ERROR: $1 did not report healthy within ${HEALTH_TIMEOUT}s"
  give_up "$1" "$2"
}

# Mark tag $1 failed and roll back to commit $2, unless the release changed the schema.
give_up() {
  local from
  from=$(git describe --tags --always "$2")
  # Marked before the rollback, so one that is cut off isn't followed by the same deploy again;
  # but a mark that can't be written (a full disk) must not stop the rollback.
  { echo "$1" >"$FAILED_MARK"; } 2>/dev/null ||
    log "ERROR: could not write $FAILED_MARK (disk full?); rolling back anyway"
  if ! git diff --quiet "$2" "$1" -- backend/migrations; then
    rm -f "$PENDING_MARK"
    log "ERROR: $1 changed the schema, so going back means restoring the pre-deploy" \
      "backup; left as is for a person (docs/runbooks/deploy.md, Rollback)"
    return 1
  fi
  roll_back "$2" "$from"
}

# Back to commit $1 (described as $2). On a release, wait for its version, so a container left
# over from the bad build can't pass for it. A checkout that isn't on a release has no version
# to wait for.
roll_back() {
  local previous='"status":"ok"'
  if [[ "$2" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    previous="\"version\":\"${2#v}\""
  fi
  git -c advice.detachedHead=false checkout --quiet "$1"
  if docker compose up -d --build && healthy "$previous"; then
    log "rolled back to $2"
  else
    log "ERROR: rolled the code back to $2 but it is not healthy either"
  fi
  rm -f "$PENDING_MARK"
  return 1
}

# The last run was cut off after the backup, so the checkout may be on the new tag while the
# old image runs. Build once more; if that was cut off already, or the rollback was, roll back
# instead, and only once: then the failed mark holds, as after any failed deploy.
# The mark is read as if anyone could have written it: the tag must be a release and the commit
# a full id (neither then reads as an option or another kind of name), and the release passes
# every check a new deploy does before anything is built.
resume_deploy() {
  local tag previous resumed head target before
  read -r tag previous resumed <"$PENDING_MARK" || true
  if ! [[ "$tag" =~ $RELEASE && "$previous" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ &&
    "$resumed" =~ ^(resumed)?$ ]]; then
    log "ERROR: $PENDING_MARK is not one this script wrote; delete it"
    return 1
  fi
  head=$(git rev-parse HEAD)
  target=$(git rev-parse --verify --quiet "refs/tags/$tag^{commit}") || target=""
  before=$(git rev-parse --verify --quiet "$previous^{commit}") || before=""
  if [ -z "$target" ] || [ -z "$before" ] ||
    { [ "$head" != "$target" ] && [ "$head" != "$before" ]; }; then
    log "ERROR: $PENDING_MARK doesn't match the checkout (deployed by hand?); delete it"
    return 1
  fi
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    log "ERROR: the checkout has local changes; not finishing the deploy of $tag"
    return 1
  fi
  if ! release_checks "$tag" "$target" "$before"; then
    return 1
  fi
  if [ "$(cat "$FAILED_MARK" 2>/dev/null)" = "$tag" ]; then
    log "finishing the rollback from $tag that was cut off"
    rm -f "$PENDING_MARK"
    roll_back "$before" "$(git describe --tags --always "$before")"
  elif [ -n "$resumed" ]; then
    log "ERROR: the deploy of $tag was cut off twice"
    give_up "$tag" "$before"
  else
    echo "$tag $before resumed" >"$PENDING_MARK"
    log "finishing the deploy of $tag that was cut off"
    git -c advice.detachedHead=false checkout --quiet "$target" --
    finish_deploy "$tag" "$before"
  fi
}

# Logs why and fails unless release $1, at commit $2, may replace commit $3 (the one deployed
# before): on main, forward from $3, not a tag deployed here before at another commit, and every
# commit since $3 signed by GitHub.
release_checks() {
  local seen unsigned
  if ! git merge-base --is-ancestor "$2" refs/remotes/deploy/main; then
    log "ERROR: $1 is not on main; not deploying it"
    return 1
  fi
  if ! command -v "$GPG" >/dev/null; then
    log "ERROR: gpg is needed to check $1 is genuine (sudo apt install gnupg)"
    return 1
  fi
  if ! git merge-base --is-ancestor "$3" "$2"; then
    log "ERROR: the checkout ($(git describe --tags --always "$3")) is not behind $1; deploy by hand"
    return 1
  fi
  # A tag moved in place fails the fetch; one deleted and made again arrives as new, so the
  # commit each tag was deployed at is remembered.
  seen=$(awk -v tag="$1" -v commit="$2" '$1 == tag && $2 != commit { print $2; exit }' \
    "$DEPLOYED_TAGS" 2>/dev/null) || seen=""
  if [ -n "$seen" ]; then
    log "ERROR: $1 was deployed here at ${seen:0:7} and now names ${2:0:7} (deleted and" \
      "made again upstream?); release tags never move, so not deploying it"
    return 1
  fi
  unsigned=$(unsigned_commit "$3" "$2")
  if [ -n "$unsigned" ]; then
    log "ERROR: $1 includes $(git rev-parse --short "$unsigned"), which GitHub didn't" \
      "sign; not deploying it"
    return 1
  fi
}

main() {
  cd "$REPO_DIR"
  exec 9>.git/auto-deploy.lock
  if command -v flock >/dev/null && ! flock -n 9; then
    log "another deploy is running"
    return 0
  fi
  if [ -e "$PENDING_MARK" ]; then
    resume_deploy
    return
  fi

  # Tags are fetched without +: a release tag that moved is refused, not deployed. That stops
  # every deploy until a person looks, which is the point: release tags never move. --prune
  # drops local v* tags deleted upstream, so a stray tag removed there blocks nothing here.
  if ! git fetch --quiet --prune --no-tags "$REMOTE" \
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
  if ! release_checks "$latest" "$target" "$current"; then
    return 1
  fi

  log "deploying $latest over $(git describe --tags --always)"
  # In the running app if it is up; otherwise in a one-off container of the current image, so
  # a release that fixes a crashing app can still go out.
  if ! docker compose exec -T app training-coach backup &&
    ! docker compose run --rm --no-deps -T app training-coach backup; then
    log "ERROR: the pre-deploy backup failed; not deploying $latest"
    return 1
  fi

  if ! { running_image >"$REPLACED_IMAGE" && echo "$latest $current" >"$PENDING_MARK"; } \
    2>/dev/null; then
    log "ERROR: could not write $PENDING_MARK (disk full?); not deploying $latest"
    return 1
  fi
  git -c advice.detachedHead=false checkout --quiet "$latest"
  finish_deploy "$latest" "$current"
}

# The checkout replaces this file; bash has read all of main() before it runs. Sourced (by
# the tests), it only defines the functions.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
  exit $?
fi
