# Connect my AI (MCP)

How to connect Claude.ai to Training Coach, what to set up first, and how to check and undo a
connection. The design is ADR-0047 C and ADR-0054; the security spec is
`docs/security/mcp-threat-model.md`. Phase C1 is read-only.

## Before the first connection (once, on the Pi side)

1. `TC_PUBLIC_URL=https://coach.vybe-dev.com` is set (it already is for web sign-in). Without
   it `/mcp`, `/oauth/*` and the metadata answer 404.
2. You have a passkey on the phone or computer you'll approve from (Account page, "Add a
   passkey"). A link from the bot can't approve a connection.
3. **Cloudflare** (dashboard, the `vybe-dev.com` zone):
   - a rate-limit rule on `/mcp` and `/oauth/*` next to the one on `/api/auth/*`, e.g. 120
     requests a minute per IP on `/mcp` and 30 on `/oauth/*` (the app limits each connection
     to 60 a minute and each address to 30 a minute per OAuth route itself);
   - nothing (WAF custom rule, Bot Fight Mode, a challenge) blocks Anthropic's egress
     `160.79.104.0/21` on `/mcp`, `/oauth/*` and `/.well-known/*`. Claude's servers can't solve
     a challenge, and a blocked metadata request shows up in Claude as "Couldn't reach the MCP
     server".
4. Check the metadata from outside:

   ```sh
   curl -s https://coach.vybe-dev.com/.well-known/oauth-protected-resource/mcp
   curl -s https://coach.vybe-dev.com/.well-known/oauth-authorization-server
   curl -si -X POST https://coach.vybe-dev.com/mcp | grep -i www-authenticate   # 401 + resource_metadata
   ```

## Connecting Claude.ai

1. In Claude (web or app): **Settings > Connectors > Add custom connector**.
2. Name: `Training Coach`. URL: `https://coach.vybe-dev.com/mcp`. Leave the client ID and
   secret empty: Claude registers itself (dynamic client registration) as a public client.
3. Claude opens our consent page (`/connect`). Check that it says the app **calls itself
   "Claude"** and sends you back to **claude.ai**. Claude's callback is
   `https://claude.ai/api/mcp/auth_callback`; Anthropic says it may move to `claude.com`, which
   the page would then show.
4. Tick what it may read. Training is ticked; body measurements and readiness (health data) are
   not, and stay off unless you tick them.
5. **Allow with your fingerprint.** You're sent back to Claude, and a Telegram message confirms
   the new connection with the name and the host.

Steps 3 to 5 must happen within 10 minutes of step 2, and the registration expires 15 minutes
after Claude made it; if either runs out, add the connector again.

## Using it

Ask Claude about your training. It calls `get_guide` first, then `get_summary`,
`get_exercise`, `get_tests`, and `get_body` or `get_readiness` if you shared them. Every call is
an `mcp.call` event (connection, tool, outcome: no data) in the export.

## Revoking, and when it ends by itself

- **Account page > Connected AI apps > Revoke** ends it at once: Claude's next call gets 401.
  A Telegram message confirms it.
- It also ends: 90 days after you approved it (approve again from Claude); when you remove the
  passkey that approved it; on `/recover`; on erasing all your data; and if its refresh token is
  ever used twice or by another app (a Telegram message says so). A refresh answer lost on the
  way also ends it (accepted: the tokens are stored only hashed); reconnect from Claude.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| "Couldn't reach the MCP server" in Claude, nothing in the app's logs | Cloudflare blocked Anthropic's egress, or `TC_PUBLIC_URL` is unset (404 on the metadata) |
| The consent page says the request expired | More than 10 minutes on the page, or it was already used: add the connector again |
| "That didn't confirm it's you" | No passkey on this device, or the fingerprint was cancelled; a bot link session doesn't count |
| Registration answers 429 | Three registrations from that address are waiting (Claude's egress is shared): wait up to 15 minutes |
| Claude stops working after a while | The connection ended (90 days, revoked, refresh reused): look for the Telegram message, then reconnect |
