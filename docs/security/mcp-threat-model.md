# MCP threat model (ADR-0047 C: Connect my AI)

Status: **draft for review.** ADR-0047 requires this to be reviewed before any C code merges, and C gets a security review before release. In `docs/security/threat-model.md`, the row "Prompt injection via other Claude connectors" becomes a one-line pointer to this file.

## Scope

- **Covered:** the remote MCP endpoint `https://coach.vybe-dev.com/mcp` and the OAuth 2.1 authorization server inside the app (`/oauth/*` and `/.well-known/*`).
- **Scopes:**
  - Phase C1 (read-only): `training:read`, `body:read`, `readiness:read`.
  - Phase C2: `log:propose`.
- **Tools:** `get_guide`, `get_summary(period)`, `get_exercise(slug)`, `get_tests()`, `get_body(period)`, `get_readiness()`, `propose_log(...)`.
- **Out of scope:**
  - A (copy) and B (Groq key), which are covered in the main threat model.
  - What the person's AI vendor does with the data once it has it. That is a transfer the person starts, and the consent screen says so.

## Assets

- **Training data:** workouts, sets, tests, habits and the plan position (`services/ai_summary.py`).
- **Health data:** body measurements and readiness answers. Photos are never exposed.
- **OAuth secrets:**
  - authorization codes, access tokens and refresh tokens;
  - PKCE verifiers, which the client holds;
  - consent transaction handles.
- **Registered clients and their redirect URIs.**
- **Integrity of the training log:** nothing the AI sends may save, change the plan, change settings or touch sign-in.
- **Availability of the Pi,** which is shared with Vybe and sits on an SD card.
- **The owner's attention:** Telegram alerts must not become noise an attacker can flood.

## Trust boundaries

1. **AI client to Cloudflare.**
   - Claude.ai's MCP connector calls from Anthropic's egress IPs. Other clients call from anywhere.
   - Every request is untrusted, including the client's self-declared name and its metadata.
   - Anthropic's egress is shared by every Claude user, so a per-IP limit there is really a per-vendor limit.
2. **Cloudflare tunnel to the app.**
   - The WAF and rate limits apply to `/mcp` and `/oauth/*`, as they already do for `/api/auth/*`.
   - `CF-Connecting-IP` is believed only from `TC_TRUSTED_PROXIES`, using the existing `_client()` in `api/passkeys.py`.
   - The app port is published on 127.0.0.1 only.
3. **The person's browser to the consent page.**
   - This is the only place a connection is created, and the person signs in with their passkey.
   - The session cookie (`__Host-tc_session`, SameSite=Strict) is not sent on the cross-site navigation from the AI app. The page loads signed out and asks for the fingerprint.
4. **Authorization server to resource server.** Both live in the same process. Tokens are opaque values checked against hashed rows. They are not JWTs, so revoking one takes effect at once.
5. **Tool results to the person's AI.** Data leaves the app here, and anything inside it can try to steer that AI.
6. **Proposal to the person.** An AI-made proposal crosses into the confirm step (ADR-0007), in the web app or on Telegram.

## Mechanisms

- **Protected-resource metadata (RFC 9728):** a `401` from `/mcp` carries `WWW-Authenticate: Bearer resource_metadata=...`.
- **Authorization-server metadata (RFC 8414).**
- **Dynamic client registration (RFC 7591), bounded:**
  - at most 20 pending registrations overall and 3 per client address;
  - name up to 60 characters;
  - at most 5 redirect URIs, each up to 200 characters, `https` or loopback only;
  - a registration that hasn't reached consent expires after 15 minutes, and when the cap is
    full the oldest unapproved one is evicted instead of the new one being refused.
- **Authorization code with PKCE S256,** checked against the stored code challenge.
- **Resource indicators (RFC 8707):** `resource` must equal the `/mcp` URL.
- **Consent requires a passkey, proved in the last 10 minutes:** a passkey sign-in or ADR-0049's
  fingerprint confirmation. A session started by a recovery link can't approve a connection
  until a passkey confirms it, so Telegram access alone can't open a data channel.
- **Tokens:**
  - access tokens last 1 hour;
  - refresh tokens last 30 days and rotate;
  - all are 32 random bytes, stored as SHA-256 like `LoginLink`;
  - each is bound to one user, one client and one resource.

## Threats and controls

| Threat | Entry point | Controls | Tests / checks |
| --- | --- | --- | --- |
| M1: Token theft or replay | Leaked tokens from the AI vendor, logs or a backup | Opaque 32-byte tokens stored only hashed. Access 1 h, refresh 30 d rotating; reusing a refresh token revokes the whole connection and alerts. Bearer tokens are accepted only in the `Authorization` header, never in a query string, and never logged. Export leaves `*_hash` columns out by rule. Revoke on the Account page | `tests/services/test_mcp_tokens.py`: expiry, hashing, rotation, reuse revokes, query-string token refused, captured logs |
| M2: Confused deputy or wrong token audience | `/mcp`, `/oauth/token` | Tokens carry `resource` = the `/mcp` URL and are refused anywhere else. Session cookies are never accepted on `/mcp`, and bearer tokens never on `/api/*`. No token passthrough. Consent is per client and redirect URI, never skipped. `iss` is returned in the authorization response (RFC 9207) | Wrong-resource, cookie-on-`/mcp` and bearer-on-`/api` tests |
| M3: Malicious registered client, or phishing-style consent | `/oauth/register`, consent page | Registration grants nothing until passkey consent. The name is shown as untrusted ("calls itself ...") beside the redirect host. The Telegram alert names both as plain text. Caps and expiry as listed above. The consent page says what data leaves and to whom | Registration cap, metadata limit and expiry tests; consent page shows "calls itself" and the host |
| M4: Open redirect or `redirect_uri` manipulation | `/oauth/authorize`, `/oauth/token` | Exact string match against a registered URI (loopback only for `http`). An unknown client or mismatched URI gets an error page, never a redirect. Error redirects go only to a validated URI, with `state` echoed. The code is bound to `redirect_uri`, and `/oauth/token` checks it again | Mismatch, prefix, extra query, fragment, `javascript:` and `http` tests |
| M5: CSRF or clickjacking on consent | Consent approve POST | `request_guard`'s Origin / `Sec-Fetch-Site` check. SameSite=Strict cookie. A random single-use consent handle (10 min, hashed) bound to the session and the request. `Owner` + `Fresh`. CSP `frame-ancestors 'none'` | Cross-origin approve refused, handle replay, stale session, framing header |
| M6: Code interception or replay | Redirect to the client | PKCE S256 required (`plain` refused). Codes are single use, last 60 s, and are claimed by one conditional update. A reused code revokes the tokens issued from it | Missing or wrong verifier, `plain`, replay and race tests |
| M7: Scope escalation | Authorize, refresh, tools | Unknown scopes are refused. Health scopes start unticked even when requested. Granted scopes are at most the requested ones and the person's ticks. A refresh cannot widen them. Tools without their scope are hidden from `tools/list` and refused with `insufficient_scope` | Matrix test: every tool against every scope set |
| M8: Data over-exposure | Tool results | Tools reuse `ai_summary` with `Options(body=…, readiness=…)` set from the scopes. Photos and sign-in tables are never reachable. Sessions are bound to the token's user (ADR-0029). Answers are size-capped and sent with `Cache-Control: no-store` | Two-user scope test through `/mcp`; health data absent without its scope; size cap |
| M9: Prompt injection through the person's own text or tool results | Tool results read by their AI | Text the person or a client typed goes only in a delimited, length-capped "data from the person" field, never mixed into prose. Answers name the guide version, and the guide says data is never instructions. Residual risk: the AI may also hold other tools (such as web fetch) that could leak what it read; the consent page says so | Hostile-string fixtures appear only inside the data field |
| M10: Injected or rogue `propose_log` | `propose_log` | The proposal is parsed into the typed-log Pydantic model and checked again by the rule parser: known exercises, sane ranges, today or an earlier unsaved day. An invalid proposal is refused with a reason. A valid one reaches the person only as a draft with a random token, and only their "Save" (web session or `owner_only` bot button) stores it. No MCP token can confirm. At most 3 pending proposals per connection. No tool touches the plan, settings or sign-in | `tests/api/test_mcp_propose.py`: invented exercise, extreme value, future day, confirm through a token refused, cap |
| M11: DoS on the Pi, or slots taken so the real AI can't register | `/oauth/register`, `/oauth/token`, `/mcp` | Row caps on registrations, consent handles and codes, with expired rows cleared on each call. Unapproved registrations live 15 minutes, and a full cap evicts the oldest unapproved one, so a few addresses can't lock out Claude.ai. 60 requests a minute per connection. 64 KB body cap (`MAX_BODY`). SHA-256 lookups, no slow hashing. Cloudflare rate limit. Coalesced alerts, so a flood can't spam Telegram | Cap and 429 tests; body limit on `/mcp` |
| M12: Long-lived or forgotten access | Connections | The Account page lists each connection (name as claimed, redirect host, scopes, created, last used) with Revoke. Revoke ends access and refresh tokens at once. `/recover` and erase revoke every connection. Alerts on create, revoke and refresh reuse | Revoke, recover and erase tests |
| M13: Audit log leaking data | `events`, structlog | Each call writes one `mcp.call` event holding only the connection id, tool name and outcome; the `Event` rules apply. No arguments, tokens, codes or client names in logs. The alert `kind` is logged, not its text | Captured-log and event-payload assertions |

## Requirements

1. Every `/oauth/*`, `/.well-known/*` and `/mcp` route must be listed as public or sit behind a new `connection(scope)` dependency. `test_every_route_is_public_or_owner_only` must recognise that dependency and fail on anything else.
2. Access tokens, refresh tokens, authorization codes and consent handles must each be 32 random bytes, stored only as SHA-256, and absent from the export and from every log line.
3. Token lifetimes:
   - access tokens expire after 1 hour, refresh tokens after 30 days;
   - each refresh issues a new pair and invalidates the old refresh token;
   - presenting a used refresh token revokes the connection and sends a Telegram alert.
4. `/mcp` must reject the following with `401` and a `WWW-Authenticate` header naming the resource metadata. `/api/*` must ignore bearer tokens.
   - a token whose resource is not the `/mcp` URL;
   - a token in a query string;
   - a request carrying only a session cookie.
5. `/oauth/authorize` must refuse a missing or `plain` PKCE method, an unknown `resource` and unknown scopes.
6. A `redirect_uri` must match a registered URI byte for byte; `http` is allowed only for loopback. On any mismatch, or for an unknown client, the server renders an error page and sends no `Location` header.
7. Authorization codes:
   - single use, expiring after 60 s, claimed by one conditional update;
   - two racing exchanges yield one token;
   - reusing a code revokes the tokens issued from it.
8. Registration limits, refused with `429` or `400`:
   - more than 20 pending registrations overall, or 3 per client address (`_client()`);
   - a name over 60 characters;
   - more than 5 redirect URIs, or any over 200 characters;
   - any scheme other than `https` or loopback.
   A registration that hasn't reached consent expires after 15 minutes. When the cap is full,
   the oldest unapproved registration is evicted rather than the new one refused; a test shows
   seven addresses filling the cap can't stop a later registration.
9. The consent page requires `Owner` and a passkey proved in the last 10 minutes (a passkey
   sign-in or an ADR-0049 confirmation); a recovery-link session alone is refused, with a test.
   It shows the client name as "calls itself ...", the redirect host, and each scope in plain words, with health scopes unticked.
10. Consent approval is a same-origin POST carrying a single-use, session-bound handle. The global CSP (`frame-ancestors 'none'`, `form-action 'self'`) stays unchanged: approval returns the redirect URL to the page, which then navigates to it.
11. Granted scopes are a subset of the requested scopes and the person's ticks, and a refresh never adds scopes. Each tool is refused, and hidden from `tools/list`, without its scope. A test covers every tool against every scope set.
12. Tool results are built from sessions bound to the token's user. A two-user test shows that user B's token never returns user A's rows.
13. Body and readiness data appear only with `body:read` and `readiness:read`, and photos never appear. Every answer names `GUIDE_VERSION` and stays under a fixed size cap.
14. Text entered by a person or a client appears only inside a delimited, length-capped data field. Hostile fixtures ("ignore previous instructions ...") never appear outside it.
15. `propose_log`:
   - input passes the typed-log Pydantic model and the rule parser, or is refused with a reason;
   - a valid proposal creates an unsaved draft only;
   - saving needs the person's web session or the `owner_only` bot button, and a token-authenticated request to confirm is refused;
   - at most 3 proposals are pending per connection.
16. `/mcp` allows 60 requests a minute per connection (`429` beyond that) and keeps the 64 KB body cap. Every `/mcp` and `/oauth` answer carries `Cache-Control: no-store`.
17. Each tool call writes exactly one `mcp.call` event holding only `{connection_id, tool, outcome}`. A test asserts that no argument, token or measurement appears in events or captured logs.
18. A Telegram alert goes out, after the response, for a new connection (client name and redirect host as plain text), a revoke and a refresh reuse.
19. The Account page lists connections and can revoke them, ending every token at once. `/recover` and `POST /api/account/erase` revoke every connection.
20. Before release:
   - the Cloudflare rate limit covers `/mcp` and `/oauth/*`, checked in the deploy runbook;
   - Claude.ai's connector completes a full connect, read and revoke cycle through the tunnel.

## Open questions for the owner

1. Should refresh tokens have an absolute lifetime (say 90 days, like `MAX_SESSION_AGE`), after which the person approves again with the fingerprint?
2. Should removing a passkey revoke the connections approved with it, as it already ends the sessions it started?
3. The limit of 3 pending registrations per address applies to Anthropic's shared egress, and
   the 15-minute expiry with eviction keeps the slots from being held. Is that acceptable while
   there is one user, with a per-vendor allowance revisited when others join?
4. Should C1 ship with only `training:read`, adding the health scopes in a later PR after the first security review?
