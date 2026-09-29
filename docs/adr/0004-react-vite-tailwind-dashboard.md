# ADR-0004: Dashboard in React + Vite + Tailwind, served by the backend

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The dashboard must look like a polished, high-end app, work well on a phone (including inside
Telegram as a Mini App), and be shareable through Cloudflare. Data lives on the Pi.

## Decision

A React 19 + TypeScript single-page app built with Vite and styled with Tailwind v4. The build
output is copied into the backend image and served by FastAPI from `/`, with the API under
`/api`. One origin, one deployment, strict CSP.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| React + Vite on the Pi (chosen) | Rich component ecosystem, one origin, no second host | Build step in the image |
| Next.js on Vercel | Matches Vybe frontend | Data on the Pi means calls back through the tunnel; two deployments; cross-origin auth |
| Server-rendered HTMX | Lightest | Hard to reach a high-end app feel, weaker charting |

## Consequences

- Visual design is decided before phase 2 build (`docs/specs/dashboard-design.md`).
- CSP forbids inline scripts; do not add libraries that need `unsafe-inline`.
