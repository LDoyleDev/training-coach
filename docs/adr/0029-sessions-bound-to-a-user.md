# ADR-0029: Per-person data is scoped by binding the session to a user

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam (direction, ADR-0026); implementation choice in #72

## Context

ADR-0026 makes every per-person table carry a `user_id`. About 40 queries across six services
read or write those tables; filtering each one by hand would mean one forgotten `where` leaks
another person's training data, and nothing would notice until a second person existed.

## Decision

- Per-person models inherit an `Owned` marker and carry `user_id`: `workouts`, `set_logs`,
  `exercise_state`, `plan_state`, `settings`, `events` (system events have none). The shared
  plan (exercises, ladders, sessions, items) is not owned.
- `make_session_factory(engine, user_id=...)` returns sessions **bound to a user**. Two
  SQLAlchemy listeners in `db/session.py` do the rest:
  - `do_orm_execute` adds `with_loader_criteria(Model, Model.user_id == user)` for every owned
    model to every select and delete, including joins, subqueries, lazy loads and
    `session.get`. ORM inserts and updates of owned models that skip the flush are refused.
  - `before_flush` stamps `user_id` on new owned rows; refuses a row for another user, a set
    on someone else's workout, and any change of an existing row's `user_id`.
- Services never filter by user themselves. Lookups that used to mean "row 1" (`plan_state`,
  `settings`, `exercise_state` by exercise) go through `services/users.py`, which relies on the
  binding.
- Unbound sessions are for shared work only: the seed (which provisions each user's rows by
  naming them explicitly), linking the owner's Telegram account at start-up, and migrations.
  A shared check that must see everyone from any session (the seed's "ladder step in use"
  guard) passes the `all_users` execution option explicitly.
- `session.get` may answer from the identity map without a query; that is safe because a bound
  session can only ever have loaded its own user's rows.
- **Covered:** ORM statements run through `Session.execute`, `scalars`, `get` and the unit of
  work. **Not covered:** string SQL (already banned by CLAUDE.md) and Core statements on
  `session.connection()`; neither may be used for per-person data.
- The app binds the bot's sessions to the owner, whose user is linked to the allowed Telegram
  account on every start (`users.link_owner`).

## Consequences

- A query that forgets the user is still scoped; tests with two users prove each sees and
  changes only their own rows: plain and joined reads, sets on their own, lookups by id,
  cached statements, bulk deletes, and the refused writes above.
- An unbound session refuses per-person rows: any ORM statement that selects from or joins an
  owned table raises unless it passes `all_users` explicitly (the seed's shared checks), so
  per-person work can't silently run unscoped.
- Event payloads are unchanged; events now record whose they are, and system events have none.
  Deleting a user cascades to all their rows, events included.
- Linking moves the owner to whatever Telegram account is allowed (recorded as
  `users.owner_relinked`). Once invites exist, another user holding that account would make
  start-up fail on the unique constraint; the invites ADR must settle relinking first.
- Migrations on SQLite now run in one real transaction from the first statement, since the
  driver would otherwise commit a leading `CREATE TABLE` on its own.
