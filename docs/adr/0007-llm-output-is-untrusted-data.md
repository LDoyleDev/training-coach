# ADR-0007: LLM output is untrusted data, never an action

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The app uses language models to parse workout logs (and later Claude via MCP). Models can be
wrong or manipulated by injected text (prompt injection).

## Decision

- Models never get tools and never trigger side effects.
- Model output must parse into a strict Pydantic schema (known exercise IDs, bounded integers)
  or it is rejected.
- Every parsed log is shown to the user and saved only after an explicit confirmation tap.
- Rule-based parsing runs first; the model is a fallback.
- The later MCP endpoint exposes only narrow tools (read, log, propose). Plan changes proposed
  via MCP require approval in Telegram. Every MCP call is audit-logged.

## Consequences

- Worst case of a bad or injected parse: a wrong row that the user sees and rejects.
- Tests include hostile inputs (instructions inside transcripts, out-of-range numbers).
