# ADR-0011: Claude GitHub Action on the owner's subscription

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

Development is done with Claude Code locally and in Claude Code on the web. Automated review
and `@claude` on issues/PRs add a second pair of eyes and allow work from the phone.

## Decision

Use `anthropics/claude-code-action`, authenticated with `CLAUDE_CODE_OAUTH_TOKEN` (from
`claude setup-token`, i.e. Liam's subscription, no API billing). Two workflows:
`claude.yml` (responds to `@claude`) and `claude-review.yml` (reviews each non-draft PR).
Both run only for events authored by the repo OWNER, never for forks, never on
`pull_request_target`. The review job has a restricted tool list. Actions are pinned to SHAs.

## Consequences

- Usage counts against the subscription's limits.
- Text from other people cannot trigger the model (prompt-injection guard).
