# Runbook: deploy to the Pi

Host: `vybe-pi` (Raspberry Pi 5, Ubuntu Server 24.04), reached over Tailscale.

## First-time setup

```bash
ssh vybe-pi
git clone git@github.com:LDoyleDev/training-coach.git ~/training-coach
cd ~/training-coach
cp .env.example .env && chmod 600 .env && nano .env   # production values, TC_ENVIRONMENT=production
mkdir -p data && sudo chown 10001:10001 data           # container runs as uid 10001
make up
curl -s http://127.0.0.1:8080/healthz
```

Cloudflare Tunnel (phase 2, when the dashboard ships): add a public hostname, e.g.
`coach.<your-domain>` -> `http://127.0.0.1:8080`, in the existing tunnel config. Enable WAF
managed rules and a rate-limit rule for `/api/auth/*`.

Host hardening checklist (once): `ufw default deny incoming`, SSH only on the Tailscale
interface, `unattended-upgrades` enabled.

## Routine deploy (after a release)

```bash
ssh vybe-pi
cd ~/training-coach
git fetch --tags && git checkout vX.Y.Z    # deploy released versions only
make up                                    # rebuilds; runs migrations + plan seed on start
make logs                                  # watch for bot.started
```

## Rollback

`git checkout <previous tag> && make up`. If the release included a migration, first restore
the pre-deploy backup (see backup-restore.md), because downgrades may drop data.
