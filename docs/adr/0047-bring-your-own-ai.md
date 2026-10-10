# ADR-0047: Bring your own AI

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam

## Context

Liam wants an AI's view of the training: Groq comments, pasting into an AI, and a Claude
connection (MCP). Once others use the app, nobody should run on Liam's Claude subscription or
Groq quota, and each person should be able to use the AI they already have.

## Decision

Every AI feature uses the person's own AI or key; the app runs no shared AI for commentary.
Three optional ways, all off by default, detailed in `docs/specs/ai-connections.md`:

- **Copy for my AI**: a compact summary to paste, linking a public guide in this repo.
- **Comments from my key**: the person's own Groq key, encrypted at rest, for short comments.
- **Connect my AI**: a remote MCP server with OAuth 2.1, passkey consent, scoped read access,
  and log proposals the person confirms.

The guide (`docs/ai-guide.md`) lives in the public repo, so the site stays private (ADR-0041).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Bring your own AI, three ways (proposed) | No shared AI cost; people choose; Liam's accounts stay his | Three features to maintain; MCP is a public OAuth surface |
| One shared AI on Liam's Groq or API key | Simplest | Others use Liam's quota or money; one key's limits for everyone |
| MCP only | One mechanism | Leaves out people whose AI app has no connectors |

## Consequences

- The app's Groq key keeps only its current jobs (transcription, log reading).
- A secrets key (`TC_SECRETS_KEY`) joins `.env` for B. It can hold several keys for rotation
  (re-encrypt with the newest, then drop the old); losing it means people re-enter their Groq
  keys. It protects a leaked database or backup, not a compromised Pi.
- C's threat-model section is written and reviewed **before any C code merges**, not only
  before it's reachable; C also gets a security review before release.
- **Tools for outside AIs.** CLAUDE.md says LLMs never get tools and never trigger actions.
  That rule is about the app's own LLM calls (Groq). An outside AI reached through C gets
  read tools, and one write, `propose_log`, which only creates a proposal: nothing is saved
  until the person confirms it in the app or on Telegram, the same confirm step as a typed
  log (ADR-0007). No tool changes the plan, settings or sign-in. CLAUDE.md's rule gets a
  pointer to this when C is built.
- The privacy notice describes each way as a transfer the person starts.
