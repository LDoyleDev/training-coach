# ADR-0001: Record architecture decisions

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The project is built mostly by Claude Code across many sessions. Without a written record,
decisions get re-litigated or silently reversed by a later session that lacks the context.

## Decision

Record every significant decision as a short ADR in `docs/adr/`, numbered, using
`template.md`. Accepted ADRs are binding; changing one means writing a new ADR that supersedes
it. New ADRs arrive in the same PR as the change they justify (use `/adr` in Claude Code).
Claude's PR review checks changes against accepted ADRs.

## Consequences

- Decisions are reviewable in PRs and visible in git history.
- A small overhead per decision; kept low by the template and the `/adr` command.
