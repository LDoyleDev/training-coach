#!/usr/bin/env bash
# One-time (idempotent) GitHub setup for LDoyleDev/training-coach.
# Requires: gh (logged in with admin rights), jq. For the project board: gh auth refresh -s project
# Usage: scripts/github-bootstrap.sh
set -euo pipefail

REPO="${REPO:-LDoyleDev/training-coach}"
OWNER="${REPO%%/*}"
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

command -v gh >/dev/null || { echo "gh is required"; exit 1; }
command -v jq >/dev/null || { echo "jq is required"; exit 1; }

say "Repository settings"
gh api -X PATCH "repos/$REPO" \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true -F allow_auto_merge=true -F allow_update_branch=true \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY \
  -F has_projects=true -F has_wiki=false >/dev/null
gh api -X PUT "repos/$REPO/vulnerability-alerts" >/dev/null || true
gh api -X PUT "repos/$REPO/automated-security-fixes" >/dev/null || true
gh api -X PATCH "repos/$REPO" --input - >/dev/null <<'JSON' || echo "  (secret scanning not available on this plan; gitleaks in CI still runs)"
{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}
JSON
gh api -X PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true >/dev/null

say "Labels"
label() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force >/dev/null; }
label "type: task"       "1d76db" "Build step from a phase spec"
label "type: feature"    "0e8a16" "New behaviour"
label "type: bug"        "d73a4a" "Something is broken"
label "type: chore"      "cfd3d7" "Maintenance, tooling, deps"
label "type: docs"       "0075ca" "Documentation only"
label "type: security"   "b60205" "Security-relevant change"
label "area: bot"        "c5def5" "Telegram bot"
label "area: api"        "c5def5" "FastAPI backend"
label "area: web"        "c5def5" "Dashboard"
label "area: db"         "c5def5" "Models, migrations"
label "area: domain"     "c5def5" "Pure domain logic"
label "area: infra"      "c5def5" "Docker, CI, deploy"
label "size: S"          "ededed" "Under 2 hours"
label "size: M"          "ededed" "Half a day"
label "size: L"          "ededed" "A day or more; consider splitting"
label "status: blocked"  "e99695" "Waiting on something"
label "status: needs-spec" "fbca04" "Needs a spec before work starts"
label "priority: high"   "d93f0b" "Do next"
label "dependencies"     "0366d6" "Dependabot updates"
label "autorelease: pending" "ededed" "release-please"

say "Milestones"
milestone() {
  local title="$1" desc="$2"
  if ! gh api "repos/$REPO/milestones?state=all&per_page=100" --jq '.[].title' | grep -Fxq "$title"; then
    gh api -X POST "repos/$REPO/milestones" -f title="$title" -f description="$desc" >/dev/null
  fi
}
milestone "Phase 1 - Daily loop" "Morning message, text + voice logging, targets, progression, backups. docs/specs/phase-1-daily-loop.md"
milestone "Phase 2 - Overview" "Dashboard, share links, baseline tests, weekly review, habits, measurements"
milestone "Phase 3 - Claude and adaptivity" "MCP endpoint, readiness check"

say "Phase 1 issues"
existing_titles="$(gh issue list --repo "$REPO" --state all --limit 500 --json title --jq '.[].title')"
issue() {
  local title="$1" labels="$2" body="$3"
  if grep -Fxq "$title" <<<"$existing_titles"; then echo "  exists: $title"; return; fi
  gh issue create --repo "$REPO" --title "$title" --label "$labels" \
    --milestone "Phase 1 - Daily loop" --body "$body" >/dev/null
  echo "  created: $title"
}
SPEC="docs/specs/phase-1-daily-loop.md"
issue "1-A Data model and migrations" "type: task,area: db,size: M" \
"**Spec:** $SPEC, step 1-A

Implement the phase 1 tables in \`db/models.py\` with one Alembic migration (with downgrade).

- [ ] Models match the data model table in the spec
- [ ] Migration upgrades and downgrades cleanly (test)
- [ ] \`alembic check\` clean in CI"
issue "1-B Seed the training plan" "type: task,area: db,size: S" \
"**Spec:** $SPEC, step 1-B · **Depends on:** 1-A

- [ ] \`training-coach seed\` loads \`seed/plan.toml\` idempotently
- [ ] Exercise states start at each ladder's \`start\`; queue pointer at the first session
- [ ] Tests: idempotency, referential integrity"
issue "1-C Session queue, targets and progression rules" "type: task,area: domain,size: M" \
"**Spec:** $SPEC, step 1-C · **ADR:** 0006 · **Depends on:** 1-A

- [ ] \`domain/queue.py\`: advance on done/rest, hold on nothing logged
- [ ] \`domain/targets.py\`: targets from last performance at the same ladder step
- [ ] \`domain/progression.py\`: ready-to-progress rule
- [ ] Table-driven tests incl. double skip, wrap-around, DST dates; 100% coverage of domain"
issue "1-D Morning message, evening nudge and settings" "type: task,area: bot,size: L" \
"**Spec:** $SPEC, step 1-D · **Depends on:** 1-B, 1-C

- [ ] Daily morning job at \`settings.morning_time\` (Europe/Berlin), rescheduled on change
- [ ] Message with targets and Start / Rest today / Swap buttons
- [ ] Evening nudge only when nothing logged
- [ ] \`/settings\`, \`/today\`, \`/week\`, \`/help\`
- [ ] Owner-only test for every handler; DST scheduling tests"
issue "1-E Text logging with confirmation" "type: task,area: bot,area: domain,size: L" \
"**Spec:** $SPEC, step 1-E · **ADR:** 0007 · **Depends on:** 1-C

- [ ] Rule parser with aliases, fuzzy match, bounded numbers
- [ ] Confirmation message with Save / Edit / Cancel; save is one transaction and advances the queue
- [ ] Table-driven parser tests incl. hostile input"
issue "1-F Voice logging via Groq" "type: task,area: bot,type: security,size: M" \
"**Spec:** $SPEC, step 1-F · **ADRs:** 0007, 0008 · **Depends on:** 1-E

- [ ] Groq client: transcription + JSON fallback parse with Pydantic schema, timeouts, retries
- [ ] Voice files deleted after use; transcripts never logged
- [ ] Typed fallback message when Groq fails
- [ ] Mocked HTTP tests incl. injection attempts"
issue "1-G Personal bests, progression prompts and /progress" "type: task,area: bot,size: M" \
"**Spec:** $SPEC, step 1-G · **Depends on:** 1-E

- [ ] Personal bests after save
- [ ] Ready-to-progress prompt with Move up / Not yet
- [ ] \`/progress\` command"
issue "1-H Nightly backups and restore drill" "type: task,area: infra,size: S" \
"**Spec:** $SPEC, step 1-H · **ADR:** 0010

- [ ] Nightly SQLite online backup with rotation (7 daily, 4 weekly)
- [ ] \`scripts/pull-backup.sh\` (desktop, over Tailscale)
- [ ] Restore rehearsed and noted in the PR; runbook updated"

say "Branch protection on main"
if ! gh api -X PUT "repos/$REPO/branches/main/protection" --input - >/dev/null <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Backend (lint, types, tests)",
      "Frontend (lint, types, tests, build)",
      "Security (secrets, dependencies)",
      "Docker image builds",
      "conventional-title"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
then
  echo "  !! Branch protection failed. Private repos need GitHub Pro (or make the repo public)."
  echo "     The pre-commit no-commit-to-branch hook still blocks local commits to main."
fi

say "Project board"
if gh project list --owner "$OWNER" --format json --jq '.projects[].title' 2>/dev/null | grep -Fxq "Training Coach"; then
  echo "  exists"
else
  if num=$(gh project create --owner "$OWNER" --title "Training Coach" --format json --jq '.number' 2>/dev/null); then
    gh project link "$num" --owner "$OWNER" --repo "$REPO" >/dev/null
    for url in $(gh issue list --repo "$REPO" --state open --limit 100 --json url --jq '.[].url'); do
      gh project item-add "$num" --owner "$OWNER" --url "$url" >/dev/null
    done
    echo "  created project #$num with all open issues"
  else
    echo "  !! Could not create the project. Run: gh auth refresh -s project   and re-run."
  fi
fi

say "Remaining manual steps"
cat <<'TXT'
  1. claude setup-token   (on your desktop), then:
     gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo LDoyleDev/training-coach
  2. Install the Claude GitHub App on this repo: https://github.com/apps/claude
TXT
