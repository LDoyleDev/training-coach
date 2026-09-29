# Runbook: one-time GitHub setup

Run `scripts/github-bootstrap.sh` from the desktop (needs `gh auth login` with admin rights on
the repo). It is idempotent. It sets:

- Repo settings: squash merge only, PR title as commit message, delete branches on merge,
  auto-merge allowed, vulnerability alerts, Dependabot security updates, secret scanning.
- Branch protection on `main`: PR required, required checks (backend, frontend, security,
  docker, PR title), linear history, no force pushes or deletions, conversations resolved.
- Labels (type, area, size, status, priority).
- Milestones: Phase 1 - Daily loop, Phase 2 - Overview, Phase 3 - Claude and adaptivity.
- Phase 1 issues 1-A to 1-H from `docs/specs/phase-1-daily-loop.md`.
- A Project board "Training Coach" linked to the repo.

Manual steps:

1. `claude setup-token` on the desktop, then
   `gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo LDoyleDev/training-coach`.
2. Install the Claude GitHub App on the repo: https://github.com/apps/claude
3. The project board needs the `project` scope: `gh auth refresh -s project`.
