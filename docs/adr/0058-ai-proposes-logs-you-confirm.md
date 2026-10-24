# ADR-0058: A connected AI proposes logs; you save or discard them

- Status: Accepted; an earlier day that has its session asks at Save time instead of refusing
  (ADR-0060, see History)
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
  parser's ranges, at most 20 sets. A day that already has its session is asked about at Save
  time (ADR-0060).
- **Cardio**: zone 2 or moderate cardio, minutes and what it was, the shape of `/api/cardio`.
  The person picks zone 2 or moderate when saving; the AI's kind is a hint (ADR-0067, see
  History).
- **Habit ticks**, as on `/api/habits`: today and the two days before.
- **Body weight and girths**, as on the Body page, with its ranges.

Anything else is refused with a short reason the AI can read and fix.

**Scope** (owner): `log:propose` is unticked on the consent page, like the health scopes, and
says nothing is saved without your tap. Existing connections don't gain it; reconnecting does.
It comes only with `training:read` (owner, after review): a proposal's answers and refusals
name exercises and sessions. The server drops it from a grant without `training:read` and
refuses a refresh that narrows to it alone; the consent page ticks training with it.

**Confirming** (owner): a valid proposal is a row in `log_proposals` (not the bot's in-memory
drafts) with a random token. It shows as a card on Today and as a Telegram message, both with
Save and Discard and both naming the app ("From “Claude”: ...", its claimed name as plain text,
cut to 40 characters) and exactly what Save writes. Saving or discarding in one place resolves
it everywhere: the other then answers "already saved" or that it has gone. Telegram's buttons go
after an answer and stay after a failed save. Saving goes through the service of that kind of
log, so /undo takes a workout back. No request with an MCP token can save or discard: `/api/*`
ignores bearer tokens and no tool does it.

**Lifetime** (owner): 24 hours, then the row is deleted whether saved or not (cleared whenever
proposals are read or written), so a button pressed after that says it has gone rather than
"already saved". At most 3 wait per connection; a 4th is refused with a reason. Revoking the
connection discards what waits, and a connection past its 90 days shows none and proposes
nothing.

**Audit** (owner): one `mcp.call` event per call (connection, tool, outcome), and
`mcp.draft_saved`, `mcp.draft_discarded` and `mcp.draft_expired` events naming only the
proposal and its connection (and where it was answered), never what it held.

Also decided while building it:

- **Saved values, not the AI's words.** The row keeps what the checks produced (exercise slugs,
  sets, minutes, habits, measurements) and a summary written by the app from those values.
  Saving re-checks through the normal service; if today's session changed meanwhile (a log, a
  rest, a swap), the proposal is discarded with a reason and nothing is written. If its day has
  its session, Save asks (replace, move or add, ADR-0060) and the proposal keeps waiting until
  it is answered.
- **Plain token, not a hash.** The token is a 32-hex-character random value like a log's
  idempotency token, and doubles as that token, so saving twice saves once. It only names the
  proposal for someone who is already signed in or is the bot's owner, so it is no credential.
- **Telegram at once, then every 5 minutes.** After each `propose_log` call the bot sends what
  waits unsent; a check every 5 minutes retries a send that found Telegram unreachable. A
  proposal is marked sent only after Telegram took it, one sender at a time.
- **Habits are ticks only.** An AI can't untick one. Resting heart rate isn't proposable: it is
  not a body weight or girth, and the band brings it (ADR-0055).
- **A measurement it replaces is named** (owner, after review). Saving a body proposal
  replaces that day's value of the same kind, as the Body page does. The card and the Telegram
  message say "Replaces the 78.4 kg saved that day"; the AI's answer never says whether
  anything was there.
- **One at a time** (review of #234). `propose_log` takes SQLite's write lock first (a no-op
  update of its connection, which also checks the connection is still live), so calls at once
  count and insert in turn and the cap holds. Save and Discard claim the row with one
  conditional update before writing anything, like the OAuth code claim; it is the one
  per-person bulk update, scoped to the person by hand. Of two taps at once only one acts, and
  a failed save rolls the claim back, so the proposal waits to be tried again.
- **Save re-checks the day.** A strength proposal for a today that has passed by Save, or a
  strength or cardio day now more than 14 days back, is discarded with a reason.
- **Telegram's refusals don't block.** A message Telegram turns down outright (not a network
  failure) is marked, logged and not tried again; the card on Today still shows it, and the
  next one still goes. Telegram hears only of proposals made, not of refusals.
- **The token travels in a body**, `POST /api/proposals/save` or `/discard` with `{token}`,
  never in a URL an access log could keep.
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

## History

- 2026-10-12, ADR-0060: a strength proposal for an earlier day that already has its session is
  no longer refused, and saving one is no longer discarded when that day got its session
  meanwhile. Save asks, on the card and in Telegram, as for any log of that day; the proposal
  waits for the answer. `workout_log.day_saved` is gone.
- 2026-10-24, ADR-0067: a cardio proposal's summary names no kind. Save writes the summary with
  the kind the person picked, zone 2 or moderate, on the card or a Telegram button; the AI's
  `cardio` is only a hint.
