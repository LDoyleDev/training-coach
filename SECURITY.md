# Security

Training Coach is a personal app: one person's training data on a Raspberry Pi. The code is
public, the site isn't (ADR-0041).

## Reporting a vulnerability

Use GitHub's private reporting: **Security → Report a vulnerability** on this repository. Please
don't open a public issue, pull request or discussion for it.

Include what you found, how to reproduce it, and what it lets someone do. You'll get an answer
within a week. This is a one-person project, so there's no bounty, but you'll be credited in the
fix if you want to be.

## What's in scope

- This repository's code: the API, the Telegram bot, the web app, the deploy and backup scripts.
- How the running site at `coach.vybe-dev.com` handles requests, **without** load testing,
  automated scanning or trying to sign in as someone else. There is one account and it isn't
  yours to test.

Out of scope: Cloudflare, GitHub, Telegram and the other services it uses (report those to
them), and missing headers or settings with no way to use them.

## How it's protected

Threats and their controls: [docs/security/threat-model.md](docs/security/threat-model.md).
Rotating secrets: [docs/runbooks/rotate-secrets.md](docs/runbooks/rotate-secrets.md).
