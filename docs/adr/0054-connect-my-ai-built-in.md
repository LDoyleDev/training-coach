# ADR-0054: Connect my AI with a hand-written MCP and OAuth server in the app

- Status: Accepted (2026-10-12)
- Date: 2026-10-11
- Deciders: Liam

## Context

Phase C1 of ADR-0047 lets a person add `https://coach.vybe-dev.com/mcp` as a custom connector
in their AI app (Claude.ai first) and approve read access with their passkey. The binding spec
is `docs/security/mcp-threat-model.md`. Claude.ai's connector (its "Authentication for
connectors" docs, checked 2026-10-11) needs:

- a `401` with `WWW-Authenticate: Bearer resource_metadata=...` to start, RFC 9728 and RFC 8414
  metadata, and PKCE S256;
- dynamic client registration (RFC 7591), or a client ID metadata document when the server
  advertises one; Claude registers as a public client (`none`) and registers again on each
  fresh connection;
- the redirect URI `https://claude.ai/api/mcp/auth_callback` (Anthropic says it may move to
  `https://claude.com/api/mcp/auth_callback`);
- a form-encoded token endpoint, `invalid_grant` for a dead refresh token, rotated refresh
  tokens, and answers within 10 seconds (30 for a refresh);
- calls from Anthropic's egress, `160.79.104.0/21`.

The app has no form parser (`python-multipart`) and no MCP library. The Pi is small and the
dependency rule is "prefer the standard library".

## Decision

- **No new dependency.** The MCP transport is written by hand: JSON-RPC 2.0 over Streamable
  HTTP, stateless, one message per `POST /mcp` and a plain JSON answer (no SSE stream, no
  session id; `GET` gets `405`). Read-only tools need only `initialize`, `ping`, `tools/list`
  and `tools/call`. The token endpoint parses its form with `urllib.parse`.
- **Opaque tokens, hashed rows** (`services/mcp_tokens.py`), not JWTs: revoking is immediate
  and there is no signing key to keep.
- **Registration, not client ID metadata documents.** The metadata doesn't advertise
  `client_id_metadata_document_supported`, so Claude registers; registrations are bounded as
  the threat model says. CIMD (fetching a URL the client names) would add an outbound fetch to
  a URL chosen by the caller.
- **The consent page is a page of the web app** (`/connect#<handle>`): `/oauth/authorize`
  checks the request, stores it behind a consent handle and sends the browser there with the
  handle in the fragment (never logged, never in a Referer). The page reuses the passkey
  ceremonies; approving returns the app's address for the page to navigate to, so the CSP
  (`form-action 'self'`) is unchanged. Errors before the redirect address is trusted are a
  plain page from the server, never a redirect.
- **Every C1 scope is advertised** in `scopes_supported`, so Claude asks for all three; the
  consent page leaves the health ones unticked, so each connection opts in. No
  `offline_access` scope: refresh tokens are always issued.
- **Open consent pages are capped per address, per app and overall** (3, 3, 40). At the
  per-app cap a new page **replaces** the app's oldest page that no browser has bound yet,
  rather than being refused: an app's id is visible in the person's address bar, so with
  refusal anyone who saw it could fill its 3 slots and block the person's next attempt; with
  replacement the person's retry always gets a page, and a page they've proved their passkey
  on is never replaced. The per-address cap refuses (`429`), so one caller holds at most 3 of
  the 40 and can't keep more than 3 waiting registrations safe from eviction.
- **Rate limits live in memory** (`domain/rate_limit.py`): one process serves everything
  (ADR-0002) and the SD card gets no writes for counting. A restart forgets the counts;
  Cloudflare's rule stays in front.
- **Refresh mistakes don't burn the token:** a refresh asking for a wider scope or another
  resource is refused before the token is used up; only a used token or another client's
  presentation revokes the connection.
- **The guide ships in the image** (`/app/docs/ai-guide.md`) so `get_guide` returns it.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| By hand, stdlib only (chosen) | No new code on the Pi; small; every line tested here | We follow MCP spec changes ourselves |
| The official `mcp` SDK (transport) | Tracks the spec; SSE and sessions for later | A framework with its own Starlette app, auth helpers and dependencies for four methods; harder to fit the route guard and the per-person sessions |
| `authlib` or similar for OAuth | Mature RFC coverage | Large surface to configure safely; we need a narrow subset with app-specific limits |
| A server-rendered consent page | No SPA route | A second way to do passkeys; CSP would need loosening for a form post to the app |

## Consequences

- C2 (`propose_log`) adds one tool and the confirm step; if it ever needs server-to-client
  messages or streaming, revisit the SDK then.
- Desktop clients (loopback redirects) stay out until the owner decides (threat model,
  decision 1); Claude Code would need a port-agnostic loopback match.
- The deploy runbook checks the Cloudflare rate-limit rule on `/mcp` and `/oauth/*`, and
  that Anthropic's egress isn't blocked by a WAF rule.
