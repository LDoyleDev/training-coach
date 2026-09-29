# Runbook: rotate secrets

Rotate immediately if a secret appears anywhere outside `.env` (chat, issue, log, commit).

| Secret | Where to rotate | Then |
| --- | --- | --- |
| `TC_TELEGRAM_BOT_TOKEN` | @BotFather -> /revoke | update `.env` on the Pi, `make up` |
| `TC_GROQ_API_KEY` | console.groq.com -> API keys: create new, delete old | update `.env`, `make up` |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` on the desktop | GitHub -> Settings -> Secrets -> Actions: replace |
| Cloudflare tunnel credentials | Cloudflare dashboard | re-run cloudflared login on the Pi |

If a secret was committed: rotate first, then remove it from history only if the repo will ever
become public (rotation is what actually protects you). gitleaks in CI should stop this.
