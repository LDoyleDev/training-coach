# Runbook: deploy to the Pi

Host: `vybe-pi` (Raspberry Pi 5, Ubuntu Server 24.04), reached over Tailscale.

`make` isn't installed on the Pi, so the commands here call `docker compose` directly (`make up`
on the desktop is the same `docker compose up -d --build`).

## First-time setup

```bash
ssh vybe-pi
git clone git@github.com:LDoyleDev/training-coach.git ~/training-coach
cd ~/training-coach
cp .env.example .env && chmod 600 .env && nano .env   # secrets only; leave TC_DATABASE_URL and TC_ENVIRONMENT commented (the image sets them)
mkdir -p data && sudo chown 10001:10001 data && sudo chmod 750 data   # container runs as uid 10001; personal data
docker compose up -d --build
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
| Public surface | The plan page, `GET /api/plan`, `/healthz`, `/signin` and `/api/auth/redeem` + `/signout` (ADR-0019, ADR-0036); everything personal needs a signed-in session |
| Web sign-in | `TC_PUBLIC_URL=https://coach.vybe-dev.com` in `.env` (needed for `/login` links). Cloudflare: a rate-limit rule on `/api/auth/*`, e.g. 10 requests a minute per IP |
| Bot | Off until `TC_TELEGRAM_BOT_TOKEN` and `TC_TELEGRAM_ALLOWED_USER_ID` are set in `.env` |
| Deploys | Automatic since 2026-10-08: the `training-coach-deploy` timer is installed (0.3.0 -> 0.10.0 was the last deploy by hand) |

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

## Automatic deploys (ADR-0030)

Merging a release PR is the deploy. Within about 15 minutes, a timer on the Pi does these steps:
- takes a backup
- checks out the new tag and rebuilds
- waits for `/healthz` to report the new version

It deploys only release tags on `main`, only forward, and never over local changes. Steady
state is silent; every deploy logs `auto-deploy: deployed vX.Y.Z`.

One-time setup on the Pi (the units assume the `vybe` user and `~/training-coach`; edit them
first if either differs; `vybe` must be in the `docker` group):

```bash
cd ~/training-coach
scripts/auto-deploy.sh            # once by hand: deploys the newest release, or prints nothing
sudo cp scripts/systemd/training-coach-deploy.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now training-coach-deploy.timer
systemctl list-timers training-coach-deploy.timer
```

Day to day:

| What | How |
| --- | --- |
| What did it do? | `journalctl -u training-coach-deploy -n 50` |
| Did a deploy fail? | `systemctl --failed`, or the journal shows `auto-deploy: ERROR` |
| Hold releases back | `sudo systemctl stop training-coach-deploy.timer` (`start` to resume) |
| Unit files changed in a release | Copy them again and `daemon-reload` (the units aren't updated by a deploy) |

When a release doesn't come up healthy, the script rolls the code back to the previous version
and the bot keeps working. If the release changed the schema, it leaves the new version in
place, because going back needs the backup it took (see Rollback). Either way, the failed tag
is saved in `.git/auto-deploy-failed` and not retried. Fix it with a new release, or deploy by
hand and `rm .git/auto-deploy-failed`.

## Deploy by hand

```bash
ssh vybe-pi
cd ~/training-coach
docker compose exec app training-coach backup   # app down? docker compose run --rm --no-deps app training-coach backup
git fetch --tags && git checkout vX.Y.Z    # deploy released versions only
docker compose up -d --build               # rebuilds; runs migrations + plan seed on start
docker compose logs -f app                 # watch for bot.started (and no seed.failed)
```

## Rollback

`git checkout <previous tag> && docker compose up -d --build`. If the release included a migration, first restore
the pre-deploy backup (see backup-restore.md), because downgrades may drop data.

## Changing the training plan

Edit `backend/src/training_coach/seed/plan.toml` in a PR (CI validates it). After deploying,
`docker compose logs app` should show `seed.applied` with the counts (`seed.unchanged` means the file already
matched the database). If it shows `seed.failed`, the app is
still running on the previous plan; fix the file in a new PR. Removing a session is rejected by
design: write a data migration that repoints the queue first.

Before any workouts are logged (no history to keep), the simpler fix is to start from an empty
database: `docker compose down`, move `data/training_coach.db` aside, `docker compose up -d --build`.
