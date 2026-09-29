# ADR-0013: uv and pyproject.toml for Python dependencies

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

Builds must be reproducible on the desktop, in CI and on the Pi.

## Decision

Use uv with `pyproject.toml` and a committed `uv.lock`. Dev tools (ruff, mypy, pytest,
pip-audit, pre-commit) live in the `dev` dependency group. Tool configuration lives in
`pyproject.toml`. The frontend uses npm with a committed `package-lock.json`.

## Consequences

- `uv sync --frozen` everywhere; a lockfile change is always reviewed in a PR.
- Dependabot updates both lockfiles weekly.
