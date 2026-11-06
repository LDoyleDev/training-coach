# ADR-0073: Each person owns their sessions; exercises are a shared catalogue

- Status: Accepted
- Date: 2026-10-25
- Deciders: Liam

## Context

The plan is one shared copy: `plan.toml`, seeded into tables with no `user_id`. Progress,
settings, blocks and logs are already per person. Multi-user chose "everyone on the owner's
plan for now, each person's own copy later" (ADR-0059, Plans). The program builder needs a plan
people can change in the app (`program-builder.md`, Decided 1: edit in the app, and import
`plan.toml` as one versioned edit), and "built for everyone" means one person's edit mustn't
change another's plan.

## Decision

- **Sessions are per person; exercises are shared.** `session_templates` and `template_items`
  become `Owned` (option A2). `exercises` and `ladder_steps` stay shared as the catalogue.
  `plan.toml` holds the catalogue and the starters (the 7-day cycle, a 3-day full body and a
  4-day upper/lower, Decided 7).
- **Plan versions are per person** (ADR-0034): every saved edit makes a version with a date and
  a short "what changed"; workouts keep the version in force on their date.
- **Joining copies a starter**, and the setup flow (option H) adjusts it. The owner's current
  plan becomes the owner's copy, with its versions.
- **The seed stops changing anyone's sessions** after the copy. A change to the catalogue (a
  new exercise, a corrected weight) reaches everyone; a change to a starter reaches only people
  who join later. The owner's own plan changes are edits in the app, or a `plan.toml` import
  that shows what would change and saves as one version.
- **Built after kit, load and places** (ADR-0071, ADR-0072; Liam, 25 Oct 2026). This is the
  step that can't be undone, so it waits until those have settled in daily use and the gym
  versions have been used. Until then the shared plan carries the home and gym versions.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A2 Per-person sessions, shared catalogue (chosen) | Few foreign keys move; scoping already enforced (ADR-0029) | Every session query is per person; the seed no longer edits the plan |
| A1 One shared plan, edited in the app | Smallest | Only works for one person |
| A3 New plan tables, several plans per person | Room for "switch plan" | Every foreign key to `session_templates` moves; a large migration with no need yet |

## Consequences

- Supersedes the "Plans" paragraph of ADR-0059 when built. Builder step 5: the migration
  copying the plan to every user, the starters in the seed, and the two-person canary test
  (multi-user L2) extended to the plan routes, with a restore drill before it.
- Steps 6 and 7 (editing, the picker) build on it.
- The builder's suggested order becomes 4, 8, 9, then 5, 6, 7, 10.

## Addendum (Liam, 5-6 Nov 2026)

- **One database.** A person's plan is their own rows in the shared tables, not new tables or a
  database per person: the binding (ADR-0029) already scopes them, the catalogue is shared and
  SQLite can't enforce keys across files, and one file means one migration, backup and restore.
  Backups hold everyone together, so a restore can bring back someone who left
  (`multi-user-plan.md`, J).
- **Nobody gets a copy of the owner's plan.** The migration refuses if anyone else exists, and the
  import from `plan.toml` is the owner's alone. A new person starts from a starter, walked through
  setup (builder step 10), and finds their own level.
- The build and what the review changed: `plans-per-person.md`.
