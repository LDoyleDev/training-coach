# ADR-0041: The site is private: no public pages

- Status: Accepted (supersedes ADR-0019's public plan page)
- Date: 2026-10-10
- Deciders: Liam (security and legal review)

## Context

ADR-0019 made the plan page at `/` public: it holds no personal data. The legal review found
that it shows Liam's name and pitches the app ("A day with the coach"), which can make the site
look business-like ("geschäftsmäßig") and so need an Impressum (§5 DDG), and that it named
Huberman and Galpin in a way that reads as endorsement. Liam chose to keep the site personal
until a launch, when a UG, an Impressum and legal documents come together.

## Decision

- **Every page and API route is behind sign-in**, except what signing in needs (`/signin`, the
  link and passkey routes) and `/healthz`. `/` opens today's session (or its sign-in); the plan
  page moves to `/plan`, in the nav; `GET /api/plan` is owner-only.
- **Out of search engines**: `X-Robots-Tag: noindex, nofollow` on every response and a robots
  meta tag in the page.
- **Credit without endorsement**: sources are named as informing the plan, with "not affiliated
  with or endorsed by"; no name in headlines or the page description.
- At launch: an Impressum with the UG's address, a privacy policy and terms (security review).

## Consequences

- No Impressum is needed while the site is a personal tool. The plan's shape stays locked by
  ADR-0019's test, in case a public page returns.
