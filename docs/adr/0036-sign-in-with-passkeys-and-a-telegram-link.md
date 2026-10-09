# ADR-0036: Sign in with passkeys, started and recovered with a Telegram link

- Status: Accepted
- Date: 2026-10-09
- Deciders: Liam
- Supersedes: the owner sign-in part of ADR-0012 (share links stay as decided there)

## Context

The web app is now the main surface (ADR-0035), on the phone and later as an app. Liam asked
for fingerprint sign-in that keeps working once the web app becomes a phone app. Running cost
must stay at zero.

## Decision

- **Everyday sign-in is a passkey (WebAuthn):** the phone's fingerprint or face unlock signs a
  challenge with a key that never leaves the device. Discoverable credentials, so no username
  is typed. The relying party is the app's domain, `TC_PUBLIC_URL`'s host.
  - Passkeys sync through Google Password Manager or iCloud Keychain, and a laptop can use the
    phone over a QR code.
  - An Android or iPhone app later uses the same passkeys once the domain publishes
    `/.well-known/assetlinks.json` or `apple-app-site-association` for it.
- **The first sign-in, and recovery, is a one-time link from the bot:** `/login` (owner only)
  replies with a link that works once, within 10 minutes. The token is in the link's fragment
  (`/signin#…`), so it never reaches server or proxy logs; the page posts it to the API. Only a
  SHA-256 hash of it is stored.
- **After a link sign-in the site offers to add a passkey.** Settings list the passkeys and the
  signed-in devices, and each can be removed.
- **Sessions:** a random 32-byte token in a cookie (HttpOnly, Secure, SameSite=Strict, path /),
  stored hashed, 30 days, renewed on use, revocable. Every API route is public or owner-only,
  and a test enforces it (as ADR-0012).
- **Inside Telegram** (a Mini App, later) sign-in uses Telegram's signed `initData`, as
  ADR-0012 allows: passkeys aren't reliable in Telegram's in-app browser.
- Not now: the Telegram Login Widget (it needs the domain registered with BotFather and adds
  little next to passkeys), passwords, and email links (for other people, later).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Passkeys + Telegram link (chosen) | Fingerprint/face; phishing-resistant; free; the same keys work in an app | Needs a first proof of identity: the Telegram link |
| Telegram link only | Simplest | A message every 30 days; no fingerprint |
| Telegram Login Widget | One tap on the site | BotFather domain setup; not a fingerprint; no app story |
| Passwords | Familiar | Phishable, leakable, a reset flow to build |
| Hosted auth (Auth0, Clerk…) | Little to build | Cost and a third party holding sign-in |

## Consequences

- New per-person tables: login links, sessions and passkeys (ADR-0029).
- New dependencies, each with a reason: `webauthn` (Python, Duo Labs, BSD-3) verifies passkey
  ceremonies server-side; `@simplewebauthn/browser` (MIT) handles the browser side.
- `TC_PUBLIC_URL` is required for sign-in: links and the passkey domain come from it.
- Cloudflare: WAF managed rules and a rate limit on `/api/auth/*`, as ADR-0012.
