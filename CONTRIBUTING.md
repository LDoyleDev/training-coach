# Contributing

This is a one-person project built mostly with Claude Code, run like a team project.

## Flow

1. **Issue first.** Every change starts from an issue (templates: task, feature, bug). Build
   tasks reference a step in a phase spec and belong to the phase milestone.
2. **Branch** from `main`: `feat/12-morning-message`, `fix/31-dst-nudge`, `docs/...`, `chore/...`.
3. **Commit** with [Conventional Commits](https://www.conventionalcommits.org/):
   `type(scope): summary`. Types: feat, fix, docs, style, refactor, perf, test, build, ci,
   chore, revert. Scopes: bot, api, web, db, domain, parser, scheduler, infra, docs.
   A `commit-msg` hook enforces this.
4. **Check** with `make check` (lint, types, tests; backend and frontend).
5. **PR** with a Conventional Commit title and the template filled in (`Closes #N`). CI and
   Claude review run automatically. Squash-merge when green.
6. **Decisions** go in an ADR in the same PR (`docs/adr/`, or `/adr` in Claude Code).

## Releases

release-please maintains a release PR from the commits on `main`. Merging it bumps the version
(SemVer), updates `CHANGELOG.md`, tags `vX.Y.Z` and publishes a GitHub Release. Deploy tags
only (see `docs/runbooks/deploy.md`). Never edit versions or the changelog by hand.

| Commit type | Version bump (pre-1.0) |
| --- | --- |
| `feat` | minor (0.1.0 -> 0.2.0) |
| `fix`, `perf` | patch |
| `feat!` / `BREAKING CHANGE:` | minor pre-1.0, major after |
| others | none |

## Claude Code

`CLAUDE.md` holds the rules. Project commands in `.claude/commands/`:
`/start-issue <n>`, `/ship`, `/adr <title>`, `/next`. On GitHub, comment `@claude ...` on an
issue or PR (owner only).
