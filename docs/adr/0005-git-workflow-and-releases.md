# ADR-0005: Git workflow, commit convention and releases

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The repo should be run like a professional project: every change reviewable, traceable to an
issue, and released with clean version numbers and a changelog, with minimal manual work.

## Decision

- Trunk-based: `main` is protected (PR required, CI must pass, linear history, no force pushes).
- One issue -> one branch -> one PR, squash-merged. PR titles are Conventional Commits
  (enforced by CI), so every commit on `main` is one too.
- release-please keeps a release PR open; merging it bumps SemVer, updates `CHANGELOG.md`,
  `version.txt`, `backend/pyproject.toml` and `frontend/package.json`, and tags `vX.Y.Z`.
- Pre-1.0: `feat` bumps minor, `fix` bumps patch. 1.0.0 = phase 2 complete and in daily use.
- Backlog in GitHub Issues; one milestone per phase; a Project board for status.

## Consequences

- Deploys are by tag: the Pi can run any released version.
- Never hand-edit versions or the changelog.
