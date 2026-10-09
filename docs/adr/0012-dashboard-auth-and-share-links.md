# ADR-0012: Dashboard auth via Telegram, read-only share links

- Status: Accepted; owner sign-in superseded by ADR-0036 (share links still stand)
- Date: 2026-09-29
- Deciders: Liam

## Context

The dashboard is public on a Cloudflare subdomain so it can be shown to others, but the data
is personal.

## Decision

- Owner sign-in: (a) Telegram Mini App `initData` verified by HMAC with the bot token and a
  freshness window, or (b) a one-time login link sent by the bot (single use, 10 minutes).
  Either creates a session cookie (HttpOnly, Secure, SameSite=Strict, 30 days).
- Sharing: `/share` in Telegram creates a read-only link: 32 random bytes, stored as a SHA-256
  hash, default expiry 7 days, revocable with `/unshare`. Share views exclude body
  measurements, photos and notes.
- Cloudflare in front: WAF managed rules and rate limiting on `/api/auth/*`.

## Consequences

- No passwords to manage.
- Every API route declares whether it is owner-only or share-visible; tests enforce it.
