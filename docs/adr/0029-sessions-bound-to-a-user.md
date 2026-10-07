# ADR-0029: Per-person data is scoped by binding the session to a user

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam (direction, ADR-0026); implementation choice in #72

## Context

ADR-0026 makes every per-person table carry a `user_id`. About 40 queries across six services
read or write those tables; filtering each one by hand would mean one forgotten `where` leaks
another person's training data, and nothing would notice until a second person existed.

## Decision

- Per-person models inherit an `Owned` marker (`workouts`, `exercise_state`, `plan_state`,
  `settings`, `events`). `set_logs` are owned through their workout. The shared plan
  (exercises, ladders, sessions, items) is not owned.
- `make_session_factory(engine, user_id=...)` returns sessions **bound to a user**. Two
  SQLAlchemy listeners in `db/session.py` do the rest:
  - `do_orm_execute` adds `with_loader_criteria(Model, Model.user_id == user)` for every owned
    model to every select, update and delete, including joins and `session.get`.
  - `before_flush` stamps `user_id` on new owned rows, and refuses a row for another user.
- Services never filter by user themselves. Lookups that used to mean "row 1" (`plan_state`,
  `settings`, `exercise_state` by exercise) go through `services/users.py`, which relies on the
  binding.
- Unbound sessions are for shared work only: the seed (which provisions each user's rows by
  naming them explicitly), linking the owner's Telegram account at start-up, and migrations.
- The app binds the bot's sessions to the owner, whose user is linked to the allowed Telegram
  account on every start (`users.link_owner`).

## Consequences

- A query that forgets the user is still scoped; tests prove each user sees and changes only
  their own rows, including bulk deletes and lookups by id.
- An unbound session sees everyone. Using one for per-person work is a bug that tests won't
  catch on their own yet; a guard that makes such access raise outside the seed and start-up is
  the follow-up step of #72.
- Event payloads are unchanged; events now record whose they are, and system events have none.
