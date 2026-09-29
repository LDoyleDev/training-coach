# ADR-0018: Claude Code guardrails: hooks, review subagents, a lean CLAUDE.md

- Status: Proposed
- Date: 2026-09-29
- Deciders: Liam

## Context

Most code in this repo is written by Claude Code. Rules that live only in prose get followed
most of the time, and "most of the time" is not good enough for secrets, applied migrations or
the changelog. The previous project (vybe-trading) showed the other failure: its CLAUDE.md grew
to 65 KB of build status, ADR lists and changelog, went stale and contradicted itself, and its
main context document (312 KB) became too big to load at all.

## Decision

- **Hooks enforce rules deterministically** (`.claude/hooks/`, registered in
  `.claude/settings.json`; standard-library Python, tested in `backend/tests/`):
  - PreToolUse `guard_protected_files.py` blocks edits to `CHANGELOG.md`, real `.env` files and
    migrations that are already on `origin/main`.
  - PostToolUse `format_edited_file.py` runs ruff (backend) or Prettier (frontend) on each edited
    file. It never blocks; `make check` stays the gate.
- **Review subagents** (`.claude/agents/`): `security-reviewer` checks the diff against the
  threat model; `migration-reviewer` checks schema changes. `/ship` runs them before opening a
  PR. They are read-only.
- **CLAUDE.md is split and capped.** The root file holds stable rules and pointers, under 150
  lines, with no status, progress or changelog. Stack rules live in `backend/CLAUDE.md` and
  `frontend/CLAUDE.md`, which Claude Code loads when working in those directories. Each file
  has a short Gotchas list that grows from real mistakes and is pruned when the cause is gone.
- **Working rules:** every bug fix starts with a failing test; PRs aim for under ~400 changed
  lines excluding lockfiles, generated files and migrations.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Hooks + subagents + capped CLAUDE.md (chosen) | Rules that matter can't be skipped; reviews are repeatable; context stays small | Hook scripts are code to maintain; hooks need Python on PATH |
| Prose rules only | Nothing to maintain | Followed inconsistently; what vybe-trading had |
| Stop hook running `make check` after every turn | Catches everything early | Minutes per turn; `/ship` already runs it |
| One large CLAUDE.md | One place to look | Loaded every session; grows stale (vybe-trading) |

## Consequences

- New protected paths are added in `guard_protected_files.py` with a test, not as prose.
- The hooks take effect only once `.claude/settings.json` registers them. Claude Code does not
  edit its own permission file, so the owner applies that change.
- The review subagents cost tokens on every `/ship`; if that becomes a problem, run
  `security-reviewer` only when the diff touches `bot/`, `api/`, `services/` or config.
