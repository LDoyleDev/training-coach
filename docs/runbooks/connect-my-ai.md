# Connect my AI (MCP)

How to connect Claude.ai to Training Coach, what to set up first, and how to check and undo a
connection. The design is ADR-0047 C and ADR-0054; the security spec is
`docs/security/mcp-threat-model.md`. Proposing logs (C2) is ADR-0058.

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
4. Tick what it may do. Training is ticked; body measurements and readiness (health data) and
   proposing logs are not, and stay off unless you tick them. A connection made before
   proposing existed doesn't gain it: add the connector again to tick it.
5. **Allow with your fingerprint.** You're sent back to Claude, and a Telegram message confirms
   the new connection with the name and the host.

Steps 3 to 5 must happen within 10 minutes of step 2, and the registration expires 15 minutes
after Claude made it; if either runs out, add the connector again.

## Using it

Ask Claude about your training. It calls `get_guide` first, then `get_summary`,
`get_exercise`, `get_tests`, and `get_body` or `get_readiness` if you shared them. Every call is
an `mcp.call` event (connection, tool, outcome: no data) in the export.

With proposing ticked, ask it to log something ("log 3 sets of pull-ups, 8 8 7"). It calls
`propose_log`; a card appears on Today and a Telegram message arrives, both with **Save** and
**Discard**. Nothing is saved until you tap Save, in either place; the other then says it's
already done. A proposal waits 24 hours, at most 3 at a time per connection; /undo takes a saved
workout back. If Claude says it was refused, the reason is in its answer (an unknown exercise,
a future day, a day already saved).

To log a run from your watch or phone app, share a screenshot of its summary with your AI
and ask it to log the run. It proposes the minutes, the distance, the average and highest
heart rate and the start time it can read; the card on Today shows them with the pace (a ride
shows its speed in km/h). When the screen shows both moving (or active) time and total (or
elapsed) time, the minutes are the moving time. You pick whether it was zone 2 or moderate:
the card marks a suggestion, from your own heart-rate zones when the average heart rate is
known ("Average 131 bpm is in your zone 2"), otherwise from your AI's hint, and says why.
Pick how it felt, 1 to 10, then Save. In Telegram, tap **Zone 2** or **Moderate** to save
(how it felt is asked on the card only). The picture stays with your AI: the coach only gets
the numbers. Check them before saving, since a misread number is saved as shown.

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
| Claude can't propose logs | Proposing wasn't ticked, or the connection is older than proposing: add the connector again and tick it |
| A proposal says "today's session changed" on Save | Today was logged, rested or swapped after it was proposed: ask Claude again |
