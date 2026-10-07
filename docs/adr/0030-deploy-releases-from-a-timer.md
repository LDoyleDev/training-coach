# ADR-0030: The Pi deploys new releases itself, from a timer

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam (asked for it, #87)

## Context

Releases are cut by merging release-please's PR, and that merge is already a deliberate
decision. Deploying still needed an SSH session on the Pi to check out the tag and rebuild, so
fixes sat unreleased on the Pi: a parser fix in 0.9.1 was released, but the Pi kept running a
version that couldn't read typed logs at all. The Pi is reached only over Tailscale, and SSH
keys there need a passphrase, so GitHub can't push to it.

## Decision

A systemd timer on the Pi runs `scripts/auto-deploy.sh` every 15 minutes. The script:

1. fetches tags and `main` from the public repo over HTTPS, so it needs no credentials;
2. exits quietly when the checkout is already on the newest `vX.Y.Z` tag;
3. deploys only a tag that is on `main`, only forward from the current checkout, and never
   over local changes;
4. takes a manual backup in the running app, and stops if that fails;
5. checks out the tag, runs `docker compose up -d --build`, and waits for `/healthz` to report
   the new version.

If the new version never reports healthy, the script rolls the code back to the previous
checkout, unless the release changed `backend/migrations`. In that case going back means
restoring the pre-deploy backup, which a person does (the deploy runbook). Either way the
failed tag is written to `.git/auto-deploy-failed` and not tried again. A newer tag, or a
deploy by hand, moves past it.

Merging a release PR is now the deploy decision. To hold a release back, stop the timer.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Pull from a timer on the Pi (chosen) | No inbound access, no secrets, no cost; same steps as the runbook | Up to 15 minutes' delay; a failure shows only in the journal |
| GitHub Actions self-hosted runner on the Pi | Deploys at once; logs on GitHub | A runner with Docker access on the Pi runs code from workflow files: a large surface for a public repo |
| Actions over Tailscale (SSH from a hosted runner) | Deploys at once | Needs a Tailscale auth key and an SSH key in GitHub secrets |
| Watchtower-style image updates | Common pattern | Needs a registry and image publishing; we build on the Pi (ADR-0003) |
| Keep deploying by hand | Nothing new | Releases don't reach the Pi until someone remembers |

## Consequences

- The units live in `scripts/systemd/` and are installed once by hand (deploy runbook).
- Rolling back a release that changed the schema stays a manual restore, as before.
- Failures are visible only in `journalctl -u training-coach-deploy` and `systemctl --failed`.
  A Telegram message on a failed deploy, or the bot reporting a new version at start, would
  make them visible. Both are possible follow-ups.
- Anyone who can tag a commit on `main` can deploy to the Pi. That is the same group that
  can merge to `main`, which branch protection guards.
