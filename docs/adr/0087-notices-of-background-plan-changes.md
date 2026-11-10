# ADR-0087: A release that changes an exercise in someone's plan tells them

- Status: Accepted
- Date: 2026-11-06
- Deciders: Liam

## Context

After ADR-0073 each person manages their own plan, and the seed never changes their sessions. The
catalogue is still shared: a release can rename an exercise or a level, or add a level, and that
reaches everyone (the reverse fly's "8 kg one arm" step became its dumbbell step on 4 Nov 2026).
Liam, 6 Nov 2026: "people should be able to manage their own plans, but if something changes in
the background, they should be notified."

## Decision

- **What tells them:** a change to an exercise in their plan, in any version: a new name, a level
  renamed, a level added. Not a corrected cue, a level's number or an exercise they don't use.
- **How:** a row in `plan_notices` for each person and change, written by the seed when it makes the
  change. It shows on Home and Plan until they tap "Got it", and goes to Telegram once if the bot
  serves them (the owner until joining's Telegram step, then each person).
- **It changes nothing itself.** A notice says what happened; their level stays where it is, and
  any choice stays theirs.
- **A migration that changes a ladder** (removing a step, as `c8d2e4f6a1b3` did) writes its own
  notices: the seed can't see what a migration already did.
- **Not a notice:** a change to `plan.toml`'s sessions. That changes nobody's plan: it waits on the
  Plan page for the owner, and reaches only people who join later (ADR-0073).
- **Their own edits** carry a short note in the version's `name`, for the history; they did it, so
  nothing tells them.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A table of notices, per person (chosen) | Each person sees only what touches their plan; "Got it" per person; erased and exported with the rest | One more table |
| One "what's new" list for everyone | Simplest | Most of it wouldn't be about their plan |
| Telegram only | No new screen | Not everyone links Telegram, and the web app is the main surface (ADR-0035) |
| Derive them from `events` | No new table | Events are an audit log with no per-person read state, and `seed.applied` is a system event |

## Consequences

- `apply_seed` compares before it writes, so it says what changed once, on the start that changes it.
- `plan_notices` is per person: in the export, gone on erase, and in the two-person canary.
- A migration that changes a step must remember its notices: the migration reviewer's to check.

## Addendum (10 Nov 2026): a change to your own cycle is a notice too (ADR-0093)

Liam, 10 Nov 2026: "if there's a change to the cycle, it should be notified". A save that adds,
removes, renames, moves or changes the kind or rest days of a session writes one `plan_notices`
row saying what changed and what's next, shown and sent like any other. So does the owner's
import when it adds, retires or puts back a session. An edit to the exercises inside a session
still tells nobody, as above.
