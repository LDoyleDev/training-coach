# ADR-0045: Uptime monitoring by a heartbeat to Healthchecks.io

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam

## Context

Failed deploys and backups alert on Telegram (#168), but nothing notices when the Pi itself, its
power or its network is down, or when the app stops answering: the alerts come from the Pi. The
security review listed an outside uptime monitor. Zero spend; nothing new reachable from outside.

## Decision

The Pi sends a heartbeat to a check on Healthchecks.io (free plan, EU-hosted) every 5 minutes:
`scripts/heartbeat.sh`, run by `training-coach-heartbeat.timer`.

- It asks the app's `/healthz` on the Pi first. If the app answers, it pings the check; if not,
  it pings the check's `/fail` URL, so Healthchecks.io alerts at once.
- When pings stop (Pi, power or network down), Healthchecks.io alerts after the grace period
  (10 minutes), by email and, if connected, Telegram. It also says when pings resume.
- The ping URL is the only setting, in `~/.config/training-coach/heartbeat.env` (mode 600):
  whoever has it can fake pings, so it's treated like a token.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Heartbeat to Healthchecks.io (chosen) | Catches the Pi, power, network and a stuck app; outbound only; EU; free | Doesn't see the public path (Cloudflare, the tunnel) |
| Outside polling (UptimeRobot) | Tests the public path end to end | The site is private, so it sees a 200 from a page that proves little; US-based; a stuck app behind a working tunnel can look up |
| Both | Most coverage | Two accounts to look after for one user |

## Consequences

- An account at healthchecks.io is needed (Liam's to create); setup is in the deploy runbook.
- A tunnel or Cloudflare outage with the Pi fine isn't detected; adding outside polling later is
  a small step if that turns out to matter.
- The heartbeat unit has no `OnFailure` alert: when a ping can't go out the network is usually
  down, and the missing pings are the alert.
