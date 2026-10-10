# ADR-0044: Erasing all my data

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam

## Context

Before anyone else uses the app, a person has to be able to erase what it holds about them
(GDPR Art. 17), as they can already download it (#169). For now there is one person, the owner,
linked to the allowed Telegram account (ADR-0009), and the bot and web app assume that person
exists with a plan state and settings.

## Decision

`POST /api/account/erase` with `{"confirm": "erase"}`, from the Account page, where the person
types the word.

- **What goes:** the user row is deleted and the database's cascade takes every per-person row
  with it: workouts and sets, tests, measurements, photos, habits, settings, events, passkeys,
  sign-in links and every signed-in browser. A test holds every `Owned` table to
  `ON DELETE CASCADE` to `users`, so a table added later can't be missed.
- **What stays:** the shared plan, and the person: the same user id and Telegram account, with
  the plan's starting rows (first session, starting ladder steps, default settings), so the bot
  and the web app keep working from a fresh start. One event, `account.erased`, with nothing
  about what was there.
- **Guarded like a passkey change:** a sign-in from the last 10 minutes (ADR-0040), the typed
  word, an alert on Telegram. This browser is signed out.
- **Backups** aren't edited: they age out. Nightly backups on the Pi and off-site copies are
  gone within 5 weeks. Pre-deploy backups and their desktop copies are kept until deleted by
  hand today; they get the same limit in a follow-up, before this is relied on.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Delete the user row, cascade, start fresh (chosen) | One statement the database checks; nothing per table to forget; the bot keeps working | Leans on every foreign key being right (a test holds them) |
| Delete table by table in the service | Explicit | A new table is forgotten silently; order matters with the restricting keys |
| Remove the person entirely, Telegram link too | Truer to "delete my account" | With one owner, the app would have no one to run for until restarted |
| Also scrub backups | Erased at once | Rewriting backups risks the copies we restore from; ageing out is the usual practice |

## Consequences

- Erasing can't be undone in the app. The latest nightly backup can still restore it for a few
  weeks, which is also what saves a mistake.
- When there are other people (invites), erasing one of them removes their Telegram link too;
  this ADR then gets a successor.
- The privacy page, when it exists, states the 5 weeks.
