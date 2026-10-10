# Runbook: rotate secrets

Rotate immediately if a secret appears anywhere outside `.env` (chat, issue, log, commit).

| Secret | Where to rotate | Then |
| --- | --- | --- |
| `TC_TELEGRAM_BOT_TOKEN` | @BotFather -> /revoke | update `.env` on the Pi, `docker compose up -d --build` |
| `TC_GROQ_API_KEY` | console.groq.com -> API keys: create new, delete old | update `.env`, `docker compose up -d --build` |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` on the desktop | GitHub -> Settings -> Secrets -> Actions: replace |
| Cloudflare tunnel credentials | Cloudflare dashboard | re-run cloudflared login on the Pi |
| `TC_SECRETS_KEY` | see below | stored AI keys are re-sealed, nobody re-enters anything |

## TC_SECRETS_KEY (stored AI keys, ADR-0047)

It encrypts the Groq keys people store for AI comments. It holds one or more keys, newest
first, so it can be rotated without anyone entering their key again:

1. Make a new key on the Pi (never paste it into chat):
   `docker compose exec app python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`
2. In `.env`, put it in front: `TC_SECRETS_KEY=<new>,<old>`, then `docker compose up -d`.
3. Re-seal every stored key with the new one: `docker compose exec app training-coach rotate-secrets`.
   It prints how many were re-sealed and how many could not be read.
4. Remove the old key from `.env` and `docker compose up -d` again.

If the key leaked, also ask people to replace their Groq keys at console.groq.com: whoever had
the database and the old key could read them. If it is lost, stored keys can't be read: AI
comments stop and each person is asked once to enter their key again; nothing else is affected.

`TC_TELEGRAM_ALLOWED_USER_ID` is not a secret, but changing it moves the owner: on the next
start the owner's whole history (workouts, ladder positions, settings) belongs to the new
Telegram account, and a `users.owner_relinked` event records the old and new ids (ADR-0029).
Change it only to move to a new Telegram account of your own.

If a secret was committed: rotate first, then remove it from history only if the repo will ever
become public (rotation is what actually protects you). gitleaks in CI should stop this.
