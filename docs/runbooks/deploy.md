# Runbook: deploy to the Pi

Host: `vybe-pi` (Raspberry Pi 5, Ubuntu Server 24.04), reached over Tailscale.

## First-time setup

```bash
ssh vybe-pi
git clone git@github.com:LDoyleDev/training-coach.git ~/training-coach
cd ~/training-coach
cp .env.example .env && chmod 600 .env && nano .env   # secrets only; leave TC_DATABASE_URL and TC_ENVIRONMENT commented (the image sets them)
mkdir -p data && sudo chown 10001:10001 data && sudo chmod 750 data   # container runs as uid 10001; personal data
make up
curl -s http://127.0.0.1:8080/healthz
```

Cloudflare Tunnel: add a public hostname, e.g. `coach.<your-domain>` -> `http://127.0.0.1:8080`,
in the existing tunnel. Only the public plan page and `GET /api/plan` are open today
(ADR-0019). When dashboard login ships, enable WAF managed rules and a rate-limit rule for
`/api/auth/*`. The app runs without Telegram secrets; the bot simply stays off until both are set.

Host hardening checklist (once): `ufw default deny incoming`, SSH only on the Tailscale
interface, `unattended-upgrades` enabled.

## Production on vybe-pi today

| What | Value |
| --- | --- |
| Checkout | `~/training-coach` on vybe-pi |
| App port on the host | `127.0.0.1:8095` (Alliona's web server already holds 8080 on this Pi) |
| Public address | `https://coach.vybe-dev.com`, via the existing Cloudflare tunnel (`/etc/cloudflared/config.yml`) to `http://localhost:8095` |
| Public surface | The plan page, `GET /api/plan` and `/healthz` only (ADR-0019); no personal data |
| Bot | Off until `TC_TELEGRAM_BOT_TOKEN` and `TC_TELEGRAM_ALLOWED_USER_ID` are set in `.env` |

Keep the port change out of the tracked `compose.yaml`: put it in an untracked
`compose.override.yaml` next to it on the Pi, which `docker compose` reads automatically:

```yaml
services:
  app:
    ports: !override
      - "127.0.0.1:8095:8080"
```

Check after any deploy: `curl -s localhost:8095/healthz` on the Pi and
`curl -s https://coach.vybe-dev.com/healthz` from anywhere.

## Routine deploy (after a release)

```bash
ssh vybe-pi
cd ~/training-coach
git fetch --tags && git checkout vX.Y.Z    # deploy released versions only
make up                                    # rebuilds; runs migrations + plan seed on start
make logs                                  # watch for bot.started (and no seed.failed)
```

## Rollback

`git checkout <previous tag> && make up`. If the release included a migration, first restore
the pre-deploy backup (see backup-restore.md), because downgrades may drop data.

## Changing the training plan

Edit `backend/src/training_coach/seed/plan.toml` in a PR (CI validates it). After deploying,
`make logs` should show `seed.applied` with the counts (`seed.unchanged` means the file already
matched the database). If it shows `seed.failed`, the app is
still running on the previous plan; fix the file in a new PR. Removing a session is rejected by
design: write a data migration that repoints the queue first.

Before any workouts are logged (no history to keep), the simpler fix is to start from an empty
database: `make down`, move `data/training_coach.db` aside, `make up`.
