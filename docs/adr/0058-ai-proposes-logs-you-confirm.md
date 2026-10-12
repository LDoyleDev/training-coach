# ADR-0058: A connected AI proposes logs; you save or discard them

- Status: Accepted
- Date: 2026-10-12
- Deciders: Liam

## Context

ADR-0047 C gives a connected AI read tools and one write, `propose_log`, under the `log:propose`
scope: nothing it sends is saved until the person confirms it. C1 (ADR-0054) shipped the read
tools. The threat model (`docs/security/mcp-threat-model.md`, M10 and requirement 15) sets the
bar: the proposal passes the typed-log model and the rule parser or is refused with a reason, it
becomes an unsaved draft with a random token, only the person's web session or `owner_only` bot
button saves it, and at most 3 wait per connection. What could be proposed, where it shows, how
long it waits and what is kept of it were open. Liam decided them on 2026-10-12.

## Decision

**What can be proposed** (owner, 2026-10-12), for today or an earlier day, never the future:

- **Strength sets**: exercises by their plan name, one number per set, in reps or seconds. They
  go through the typed-log model (`groq.Rewrite`) and the rule parser under a date line of the
  app's own (ADR-0033), so they are judged exactly as a typed log: known exercises, the
  parser's ranges, at most 20 sets. An earlier day is refused once a planned session or rest day
  is saved for it.
- **Cardio**: zone 2 or moderate cardio, minutes and what it was, the shape of `/api/cardio`.
- **Habit ticks**, as on `/api/habits`: today and the two days before.
- **Body weight and girths**, as on the Body page, with its ranges.

Anything else is refused with a short reason the AI can read and fix.

**Scope** (owner): `log:propose` is unticked on the consent page, like the health scopes, and
says nothing is saved without your tap. Existing connections don't gain it; reconnecting does.

**Confirming** (owner): a valid proposal is a row in `log_proposals` (not the bot's in-memory
drafts) with a random token. It shows as a card on Today and as a Telegram message, both with
Save and Discard and both naming the app ("From “Claude”: ...", its claimed name as plain text,
cut to 40 characters) and exactly what Save writes. Saving or discarding in one place resolves
it everywhere: the other then answers "already saved" or that it has gone. Telegram's buttons go
after an answer and stay after a failed save. Saving goes through the service of that kind of
log, so /undo takes a workout back. No request with an MCP token can save or discard: `/api/*`
ignores bearer tokens and no tool does it.

**Lifetime** (owner): 24 hours, then the row is deleted whether saved or not (cleared whenever
proposals are read or written). At most 3 wait per connection; a 4th is refused with a reason.
Revoking the connection discards what waits.

**Audit** (owner): one `mcp.call` event per call (connection, tool, outcome), and
`mcp.draft_saved`, `mcp.draft_discarded` and `mcp.draft_expired` events naming only the
proposal and its connection (and where it was answered), never what it held.

Also decided while building it:

- **Saved values, not the AI's words.** The row keeps what the checks produced (exercise slugs,
  sets, minutes, habits, measurements) and a summary written by the app from those values.
  Saving re-checks through the normal service; if today's session changed meanwhile (a log, a
  rest, a swap) or an earlier day got its session, the proposal is discarded with a reason and
  nothing is written.
- **Plain token, not a hash.** The token is a 32-hex-character random value like a log's
  idempotency token, and doubles as that token, so saving twice saves once. It only names the
  proposal for someone who is already signed in or is the bot's owner, so it is no credential.
- **Telegram at once, then every 5 minutes.** After each `propose_log` call the bot sends what
  waits unsent; a check every 5 minutes retries a failed send. A proposal is marked sent only
  after Telegram took it, one sender at a time, so nothing goes twice.
- **Habits are ticks only.** An AI can't untick one. Resting heart rate isn't proposable: it is
  not a body weight or girth, and the band brings it (ADR-0055).
- **Too big is refused, not cut.** A proposal whose summary would pass 1,000 characters is
  refused, so the card always shows all that Save writes.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Rows in the database (chosen) | Seen on Today and in Telegram alike; survives a restart; one place resolves it | A table and a sweep |
| The bot's in-memory drafts (`logging_flow`) | Already there | Only Telegram; lost on restart; the web can't see them |
| Save straight away with Undo | One step less | An injected call writes data; breaks ADR-0007 and ADR-0047 |
| Recompute the proposal at save time | Always fits today | What is saved could differ from what the card showed |

## Consequences

- `CLAUDE.md`'s note on outside AIs now names `propose_log` beside the read tools.
- The export lists waiting and resolved proposals of the last 24 hours (`ai_log_proposals`).
- A proposal for today's planned session goes stale if today changes before Save; the person
  asks the AI again.
