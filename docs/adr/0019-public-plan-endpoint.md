# ADR-0019: The bundled training plan is public at GET /api/plan

- Status: Superseded by ADR-0041 (the site is private)
- Date: 2026-10-05
- Deciders: Liam

## Context

ADR-0012 puts dashboard data behind Telegram login or a read-only share token, because it holds
personal data: workout logs, progress and, later, body measurements and photos. The landing
page shows the training plan to visitors before any login exists, and that page is the one
Liam shares with people. The plan is a static file (`seed/plan.toml`) shipped in the image and
public in the repo already.

## Decision

`GET /api/plan` is unauthenticated and returns only the bundled plan: sessions in queue order,
exercises with prescriptions and ladders, the starting rung of each ladder (`start_step`) and
the weekly sets per muscle group computed from the file.

It never returns per-user data: no current progress, logs, measurements, photos or settings.
Anything user-specific gets its own endpoint behind ADR-0012 auth. A test locks the response
fields, so adding one is a deliberate change to that test and this ADR.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Public static plan (chosen) | Landing page works without login; nothing private exposed | Must keep user data out of this endpoint |
| Plan behind auth | One rule for all endpoints | Visitors see nothing; the page can't be shared |
| Bake the plan into the frontend build | No endpoint at all | Plan and page drift; two copies of the data |

## Consequences

- The live position in the cycle and real ladder progress need a separate authenticated
  endpoint (phase 1 dashboard work). The public page labels ladder rungs as starting points.
- Security headers apply as for every route. The response is small and computed from a cached
  in-memory plan, so it adds no database load; Cloudflare sits in front of it.
