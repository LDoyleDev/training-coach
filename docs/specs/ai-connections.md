# AI connections: bring your own intelligence

Status: **agreed 2026-10-10** (ADR-0047): the order below, Groq only for B, and an editable
prompt in A. Built: A (#187); B with the weekly comment (morning comments not yet).

This widens phase 3's "MCP endpoint for Claude": each person connects **their own** AI, so
nobody runs on Liam's Claude subscription or Groq quota.

## Goal

A person can get an AI's view of their training in whichever way suits them, and their AI
understands the numbers because it can read a guide to how the app works. Three ways, all
optional, all off by default, all per person:

| Way | What the person does | Whose AI, whose cost |
| --- | --- | --- |
| A. Copy for my AI | Taps "Copy for my AI", pastes into any chat (Claude, ChatGPT, Gemini, a local model) | Theirs; the app runs no AI |
| B. Comments from my key | Pastes their own Groq API key once; the weekly review and morning message gain a short AI comment | Their Groq account (free tier) |
| C. Connect my AI (MCP) | Adds the app as a connector in their AI app and signs in with their passkey | Theirs; the Pi only answers requests |

Liam uses the same three, with his own accounts. The app's own Groq key stays for what it does
today (voice transcription, reading logs the rules can't), not for commentary.

## The guide (shared by all three)

`docs/ai-guide.md` in this repo, read at `https://github.com/LDoyleDev/training-coach/blob/main/docs/ai-guide.md`
(the repo is public, so the site stays private: ADR-0041 needs no exception). It explains:

- what each field means and its unit (reps, seconds, minutes, metres, tenths of a kg/cm);
- ladders and steps, the progression rule (ADR-0027), blocks (ADR-0028), the queue (ADR-0006);
- test days and conditions, and why "not comparable" matters;
- what the readiness answers mean and that the app advises, not diagnoses;
- **how to behave**: suggest, don't prescribe; refer to a doctor on any readiness "yes", chest
  pain, dizziness; never invent data; say when there's too little to judge;
- a version number. The export and every MCP answer name the guide version they match.

No personal data, ever. A test fails if the guide's version and the export format's drift.

## A. Copy for my AI

- Account page: "Copy for my AI" with a period (last 4 weeks / 12 weeks / everything) and two
  ticks, both off: "include body measurements", "include readiness answers" (health data).
- An editable question at the top (default: review the period, what's working, what to
  change), then compact Markdown: a header line with the guide link and version, then the plan
  position, each exercise's step and recent sessions, test days, habits. Typically 2-6k tokens.
- Built on the server (`services/ai_summary.py`, `GET /api/account/ai-summary`), so B and C
  reuse the same tested summary; the browser adds the question and copies. Photos never.

Pros: works with every AI, no secrets, no new attack surface, nothing to revoke.
Cons: manual; the person must remember to paste fresh data; the copied text then lives in their
AI's history (their choice, said on the button).

## B. Comments from my key (Groq, bring your own key)

- Account page: "AI comments" with a field for a Groq key, a "test it" button, and an on/off.
  Optional ticks for which data the comment may see (measurements off by default).
- The key is **encrypted at rest** (Fernet, AES-128-CBC + HMAC; `cryptography`, today only
  a dependency of `webauthn`, becomes a direct dependency with B, so it can't vanish with a
  `webauthn` change) with a key from `TC_SECRETS_KEY` in `.env`, never in the
  database or backups in the clear, never logged, never shown again (only "ends in ...4f2a").
  This protects against a leaked database or backup, **not** a compromised Pi: the key and the
  database sit on the same host.
- **Rotation:** `TC_SECRETS_KEY` holds one or more keys, newest first (`MultiFernet`): add a new
  key, run `training-coach rotate-secrets` (re-encrypts every stored key with the newest), then
  remove the old one. Steps go in `docs/runbooks/rotate-secrets.md` with the feature.
- **Lost key:** stored Groq keys can't be read. Comments stop, each person is told once and
  asked to enter their key again; nothing else is affected.
- The Pi calls Groq with the person's key, a fixed system prompt (`backend/src/training_coach/prompts/weekly_comment.md`,
  versioned) that includes the guide's rules, and the same compact summary as A.
- Output is untrusted text: length-capped, shown as "AI comment (from your Groq key)", never
  acted on, never stored as data, links removed. One call per weekly review (the last 4
  weeks); at most one per morning if morning comments are added.
- If the key fails (revoked, quota), the comment is skipped and the person told once.

Pros: automatic; free for the person on Groq's free tier; small change on our side.
Cons: we hold a third-party secret (encrypted, but a Pi compromise with `.env` exposes it);
small models give shallow comments; their data goes to Groq under **their** account. Other
providers (OpenAI-compatible APIs) later through the same field, if wanted.

## C. Connect my AI (remote MCP server)

An MCP endpoint at `https://coach.vybe-dev.com/mcp`, per the MCP authorization spec: OAuth 2.1
with PKCE, protected-resource metadata (RFC 9728), dynamic client registration (RFC 7591) so AI
apps can register themselves, and resource indicators (RFC 8707) so tokens only work here.

**Connecting**
1. The person adds the URL as a custom connector in their AI app (Claude, ChatGPT and others
   support remote MCP connectors; availability depends on their plan).
2. The AI app opens our consent page. The person **signs in with their passkey** (a fresh
   sign-in, like passkey changes), sees the app's name and the scopes, and approves.
3. They get a Telegram alert and the connection appears on the Account page, revocable.

**Scopes** (the consent page shows them in plain words; health scopes unticked by default)
- `training:read`: plan, position, sessions, sets, tests, habits, progress.
- `body:read`: measurements (health data). Photos are never offered.
- `readiness:read`: readiness answers (health data).
- `log:propose`: propose a workout log. **Proposals don't save**: they appear in the web app
  and on Telegram as "Your AI wants to log ... Save?" and wait for the person (the bot's
  confirm step, ADR-0007). Nothing the AI sends changes the plan, settings or sign-in.
  A proposal is treated like any LLM output (ADR-0007): parsed into the same Pydantic model as
  a typed log, re-checked by the rule parser (known exercises, value ranges, today or an
  earlier unsaved day), and refused with a reason if it doesn't validate. Only a valid
  proposal reaches the person, and only their "Save" stores it.

**Tools** (small, read-mostly): `get_guide`, `get_summary(period)`, `get_exercise(slug)`,
`get_tests()`, `get_body(period)` (with `body:read`), `get_readiness()` (with
`readiness:read`), `propose_log(...)` (with `log:propose`).

**Tokens and limits**
- Access tokens 1 hour, refresh tokens 30 days and rotating (a reused refresh token revokes the
  whole connection), both stored hashed like sign-in links; bound to one person and one client.
- Redirect URIs must match exactly what the client registered; https only (localhost for
  desktop apps). The consent page sets `frame-ancestors 'none'` (no clickjacking).
- Per connection: 60 requests a minute, answers capped in size; Cloudflare rate limit on `/mcp`
  and `/oauth/*` like `/api/auth/*`. Every call is an event (tool, time, no data) on the
  Account page.
- Dynamic registration is open (the spec expects it), but bounded: at most 20 pending (not yet
  approved) registrations overall and 3 per client address, metadata capped (name 60
  characters, at most 5 redirect URIs of 200 characters, https or localhost only), and
  unapproved registrations expire after a day. A registered client can do nothing until a
  person approves it with their passkey.
- **The client's name is the client's own claim.** Anyone can register a client called
  "Claude". The consent page shows the name as untrusted ("calls itself ...") next to the
  redirect address it will send the person back to, and the alert names both; the person
  revokes anything they don't recognise.

Pros: the richest: the AI asks what it needs, when it needs it; works from the AI app on the
phone; the person's own AI and plan pay; revocable per connection.
Cons: the most work and the largest new attack surface (a public OAuth server); AI apps differ
in MCP support and change often; data leaves to the AI vendor on every call (the person's
choice, shown at consent); prompt injection: a malicious document in the person's AI could
make it call `propose_log`, which is why proposals never save on their own.

## Security across all three

| Risk | Control |
| --- | --- |
| Other people using Liam's AI accounts | No shared AI for commentary: A uses the person's AI, B their key, C their AI app. The app's own Groq key is never used for another person's comments. |
| Health data leaving without meaning to | Off by default everywhere; separate ticks/scopes; consent text names what leaves and to whom; photos never |
| Stolen MCP or Groq credentials | Hashed (MCP) or encrypted (Groq) at rest; short-lived access tokens; rotation with reuse detection; revoke on the Account page; erase removes all |
| An AI acting on its own | Read-mostly tools; writes are proposals the person confirms; no tool touches plan, settings or sign-in |
| Prompt injection through our data | Most text is ours (exercise and session names), but some is the person's own (habit names, notes, device labels): the summary and MCP answers mark it as data from the person, and the guide tells the AI to treat all data as data, never as instructions. AI output shown to the person is labelled and never executed; `propose_log` is the one write and is validated, then confirmed |
| Abuse of the public endpoints | Passkey-gated consent, rate limits (app and Cloudflare), size caps, registrations expire, alerts on every new connection |
| Our legal position | A and C are transfers the person starts to a provider they chose; B is processing on their instruction with their account. The privacy notice says so (draft in `docs/legal/`). |

## Suggested order

1. The guide + A (copy for my AI): small, no new surface, useful at once. Liam can try it today.
2. B (Groq with your own key) in the weekly review: one secret to protect, clear value.
3. C read-only (`training:read`, then the health scopes).
4. C `log:propose` with confirmation.

Each is its own PR with tests; C gets a threat-model section and a security review before it's
reachable.

## Decided (2026-10-10)

- Order as above.
- B is Groq only for now; other providers can come later through the same field.
- A starts with a short, editable question ("Review my last 4 weeks: what's working, what
  should I change?") above the data.

Still open: whether C is tested with ChatGPT as well as Claude before it's released.
