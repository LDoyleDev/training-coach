# ADR-0020: Dashboard API types are generated from the OpenAPI schema

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The dashboard calls the FastAPI backend. Until now its types were copied by hand (`Health` in
`App.tsx`), so a backend change could silently break the dashboard: both sides type-check on
their own, and nothing compares them. Changes often touch one side at a time and rely on the
type checker to catch the other.

## Decision

- `training-coach openapi` prints the API schema. It builds settings from the class defaults
  only (never `.env` or `TC_` variables) and pins `info.version`, so the output depends only
  on the code.
- `make api-types` writes it to `frontend/src/api/openapi.json` and generates
  `frontend/src/api/schema.d.ts` with `openapi-typescript`. Both files are committed.
- `make check` and the CI frontend job run `make api-types-check`, which fails when the
  committed files differ from what the code produces.
- Dashboard code takes API types from `components['schemas'][...]` and never redeclares them.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| openapi-typescript, committed output, drift check (chosen) | Types only, no runtime code; API changes show up in PR diffs; CI catches drift | Two generated files to commit; needs an npm override (below) |
| Generated client (orval, openapi-fetch + codegen) | Typed fetch calls too | Much more generated code for a handful of endpoints; add later if needed |
| Hand-written types | Nothing to set up | The drift this ADR exists to stop |
| Generate at build time, don't commit | No generated files in git | API changes invisible in review; build needs the backend toolchain |

## Consequences

- Changing a response model means running `make api-types` and committing the result;
  `make check` says so if you forget.
- `openapi-typescript` 7 declares a peer dependency on TypeScript 5. `package.json` overrides
  it to use the project's TypeScript 6, since the generator only uses the compiler's printer
  API. Remove the override once upstream supports TypeScript 6.
- The CI frontend job now also installs the backend (uv) to export the schema.
