# ADR-0088: Leaving deletes a member outright, and a list outside the database keeps them gone

- Status: Accepted
- Date: 2026-11-07
- Deciders: Liam (the decisions in ADR-0059 and `docs/specs/multi-user-plan.md` J); the details
  here follow from them
- Succeeds: ADR-0044 for members (the owner's erase stays a fresh start)

## Context

ADR-0059 decided that a member can leave at once, and that an admin can remove a member after
telling them and offering the export. Either way the user row is deleted and everything cascades,
with no fresh start. It left two things to be recorded when built: how leaving works, and the
list of left ids that is re-applied after a restore.

A restore puts back a database from before someone left, and them with it. Two facts shape the
list:
- **Ids are used again.** `users.id` is a plain SQLite integer key: a new person gets the highest
  id plus one. AUTOINCREMENT wouldn't help, because its counter (`sqlite_sequence`) is in the same
  file and a restore resets it too. So after a restore, someone new can get a left person's id.
- **Backups are the database file only.** A list kept in the database rolls back with it, losing
  exactly the people who left after the backup. A file kept only on the Pi is lost with the SD
  card, which is the case an off-site restore exists for.

## Decision

- **Leaving** (`services.erase.leave`): only a member can leave; the owner erases instead
  (ADR-0044). Their rows go by the same cascade as erase, with no fresh start. The invite they
  joined with goes too: it held the label the admin knew them by.
- **The left list** is `left-users.json`, next to the database (outside `backups/`). Each entry
  holds the id, when they joined and when they left, nothing else. It is written before the rows
  are deleted, so a delete that then fails leaves them listed, never the other way round. An entry
  is dropped 42 days after the leave: backups age out within 5 weeks, plus a week to be safe.
- **A person counts as back only if both the id and the join time match** an entry. Someone new
  on a left person's id never matches.
- **The off-site job copies the list each night**, encrypted like the backups, as
  `left-users.json.age`, replacing the last copy. After an off-site restore, the list comes from
  there.
- **Putting the list back is a deliberate step after a restore, not automatic.** `training-coach
  forget-left` names who is back, and `forget-left --apply` deletes them. At start-up the app only
  logs an error and tells the owner if anyone listed is back. It deletes nobody by itself.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A file beside the database, copied off-site, matched by id and join time, applied by hand (chosen) | Survives a restore and the SD card; can't take a new person; nothing deleted by surprise | A step to remember after a restore (the runbook and the start-up alert carry it) |
| A table in the database | No file to manage | Rolls back with the restore: loses the people who left after the backup |
| The file only, re-deleted at every start-up by id | Nothing to remember | Deletes a new person who got a left person's id after a restore; lost with the SD card |
| AUTOINCREMENT on `users` | Ids not reused in normal running | Its counter is restored with the file, so it doesn't fix reuse after a restore; a table rebuild for no gain here |

## Consequences

- `docs/runbooks/backup-restore.md` gains a step after every restore: run `forget-left`, then
  `forget-left --apply` if it names anyone.
- A person who leaves after the night's off-site copy and before the next one, on a day the SD card
  also dies, isn't on the copy. That needs both to happen within a day, and the backup restored
  would have to be from before they left.
- The list holds ids and two times for up to 42 days. That is personal data, kept only to honour
  the leave.
