# ADR-0050: Share progress as a picture, not a link

- Status: Accepted (supersedes the share links in ADR-0012)
- Date: 2026-10-11
- Deciders: Liam

## Context

ADR-0012 planned read-only share links: a `/share` command making a hashed, expiring token
and a public view of the dashboard. That means a public, unauthenticated surface on the Pi,
token storage, expiry and `/unshare`, and a view that must never leak measurements or photos.
When asked, Liam picked "screenshot-style share": the bot sends a progress image.

## Decision

`/share` in the bot replies with a PNG of the last 4 weeks, drawn on the Pi with Pillow. The
person forwards it wherever they like.

- **In it:**
  - planned sessions done, plus any extras;
  - zone 2 and moderate cardio minutes;
  - up to 8 exercises with their step on each ladder.
- **Never in it:** body measurements, readiness answers, photos, notes or habits.
- No link, no token, no public route: the image is all that leaves, and only because the
  person sends it on.
- Owner-only, like every command.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A picture from the bot (chosen) | Nothing public on the Pi; works in any chat; nothing to revoke | A snapshot, not live; a new dependency (Pillow) |
| Share links (ADR-0012) | Live view, richer | A public surface, tokens and expiry; a view that must hide data forever |
| A screenshot of the web app | No work | Shows whatever is on screen, body data included |

## Consequences

- Pillow is a new dependency (pure wheels for arm64 and x86). The default font is Pillow's
  bundled one, so no font files are added.
- ADR-0012's share-link part is not built; "every API route declares owner-only or public"
  stays as it is, with no share-visible routes.
