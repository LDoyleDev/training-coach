# ADR-0018: Develop in WSL 2 on the Windows desktop

- Status: Accepted
- Date: 2026-10-05
- Deciders: Liam

## Context

Development moves from the Ubuntu install to Windows on the same desktop. The PC should stay
on so Claude Code can be driven from the phone (Remote Control). The repo's tooling (Makefile,
uv, Docker, shell scripts, pre-commit) assumes Linux.

## Decision

Develop inside WSL 2 (Ubuntu 24.04), with the repo cloned in the Linux filesystem (`~/code`).
Claude Code runs inside WSL. Docker Desktop provides Docker through its WSL 2 backend.
Setup: `docs/runbooks/dev-environment-windows.md`.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| WSL 2 (chosen) | Same Linux toolchain as CI and the Pi; Makefile and scripts unchanged; Claude Code sandboxing supported | A VM to keep running |
| Native Windows | No VM | `make` and shell scripts need rewrites or Git Bash; behaviour drifts from CI |

## Consequences

- No code changes; CI stays the reference environment.
- A new Tailscale IP for the desktop; anything pointing at the old one must be updated.
