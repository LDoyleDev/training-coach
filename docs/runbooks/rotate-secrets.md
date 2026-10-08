# Runbook: rotate secrets

Rotate immediately if a secret appears anywhere outside `.env` (chat, issue, log, commit).

| Secret | Where to rotate | Then |
| --- | --- | --- |
| `TC_TELEGRAM_BOT_TOKEN` | @BotFather -> /revoke | update `.env` on the Pi, `docker compose up -d --build` |
| `TC_GROQ_API_KEY` | console.groq.com -> API keys: create new, delete old | update `.env`, `docker compose up -d --build` |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` on the desktop | GitHub -> Settings -> Secrets -> Actions: replace |
| Cloudflare tunnel credentials | Cloudflare dashboard | re-run cloudflared login on the Pi |

`TC_TELEGRAM_ALLOWED_USER_ID` is not a secret, but changing it moves the owner: on the next
start the owner's whole history (workouts, ladder positions, settings) belongs to the new
Telegram account, and a `users.owner_relinked` event records the old and new ids (ADR-0029).
Change it only to move to a new Telegram account of your own.

If a secret was committed: rotate first, then remove it from history only if the repo will ever
become public (rotation is what actually protects you). gitleaks in CI should stop this.
