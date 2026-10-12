# ADR-0059: Invite-only members, behind a switch that is off by default

- Status: Accepted (2026-10-12)
- Date: 2026-10-12
- Deciders: Liam
- Supersedes: ADR-0009's single allowed user (long polling stays as decided there)

## Context

ADR-0026 made the app multi-user ready and kept it to one person until an ADR for invites
superseded ADR-0009 (the bot answers one Telegram account). Every per-person table is scoped by
binding the session to a user (ADR-0029), and every web route already works for whoever is
signed in. What is missing is a way in for anyone but the owner, and the places that still
assume one owner: the bot's filter, its jobs, alerts, drafts, and relinking the owner's
Telegram at start-up, which ADR-0029 left for this ADR.

`docs/specs/multi-user-plan.md` audits the code and sets out the options. Liam answered its
questions on 2026-10-12: all as recommended except plans. This ADR records the decisions; the
plan keeps the options and the build order.

## Decision

**A switch.** `TC_MULTI_USER`, off by default, is the kill switch. Off: invites can't be made or
redeemed, members get no messages or bot replies, and only the owner's jobs run, except the
member wind-down below. Every L2 change merges behind it, so nothing changes for the owner until
it is turned on. Turning it off with members still there:
- Members are told (Telegram if linked, and a notice on their next sign-in) that the app is
  closing to them, with the date their data will be erased: 30 days from the switch going off,
  recorded per member as `closing_on`.
- For those 30 days a member can still sign in with their passkey, but only to an export-only
  Account page: download the export, or leave now (erase at once). Every other route refuses
  them. The owner never runs or receives a member's export.
- A daily wind-down job runs whatever the switch says. It erases each member whose `closing_on`
  has passed (the same cascade as leaving) and does nothing else. With no members it does
  nothing.
- Turning the switch back on within the 30 days clears `closing_on` and restores access.

**Who.** At most 5 members besides the owner (`TC_MAX_MEMBERS`), adults only (checked at sign-up).

**Invites.** Only admins invite. An invite is a one-time link (`/join#token`): 32 random bytes,
stored as SHA-256, single use, valid 72 hours, revocable, with an optional label ("Mum") for
the owner's list. Sent by any messenger; no email. Redeeming it shows the privacy notice, checks
the person is an adult, creates the user and their starting rows, starts a web session and asks
for a passkey straight away. The invites table is shared, not per person.

**Roles.** A `role` column on `users`, admin or member. The owner is the one admin. Admins make
and revoke invites, remove members, issue recovery links and get ops alerts. They can't read or
change a member's data.

**What the owner sees.** The number of members and open invites, and per member only the label
and the day they joined. Nothing of their training, body, health or band data; no "last active".
The privacy notice says plainly that whoever runs the Pi can technically read the database and
backups, that the app offers no way to, and that nobody does.

**Plans.** Everyone starts on the owner's plan with their own progress: their own place in the
queue, ladder steps, settings, tests and blocks. Each person having **their own plan** (a copy
they can change) is the goal for later and is not built now. Until then, new code takes the
person's plan where that costs no more than assuming one global plan, so the later change is
not made harder.

**Telegram.** Optional. One bot, many private chats: a member connects from Account with a
one-time token (hashed, 10 minutes) in a `t.me/<bot>?start=<token>` link; the bot then finds
the user from the sender of every update and uses a session bound to them. `/start <token>` is
the only thing a stranger can reach. Members without Telegram get no reminders until Web Push.

**Relinking (settles ADR-0029).** `TC_TELEGRAM_ALLOWED_USER_ID` is the owner's first link
only. If it names an account another user already holds, start-up logs an error and keeps the
existing link instead of failing on the unique constraint; it never takes a member's link.

**Voice.** Members use the app's Groq key with a cap of 20 voice and fallback parses a day per
member; above it, "type it instead". AI comments stay on each person's own key (ADR-0047 B).

**Recovery.** An admin-issued recovery link (single use, 24 hours, the same rules as `/recover`:
signs out other browsers, removes passkeys, alerts), plus `/recover` for members with Telegram.
Whoever holds the link can register a new passkey, so an admin could mint one and use it to sign
in as the member. The controls make that visible rather than impossible:
- The admin hands the link to the member themselves, the way the invite went. A browser signed in
  as an admin can't redeem a recovery link (it says to open it on the member's device).
- The member is told on Telegram (if linked) when a link is made for them and again when it is
  used, so an unexpected link is noticed before or as it happens.
- After a recovery, Account shows the member "Your account was recovered with a link from the
  admin on <date>" for 30 days; it can't be dismissed, so an admin who signed in that way can't
  hide it. Making and using a link are events in the member's own sign-in history.
- Residual risk, said plainly in the privacy notice next to the Pi and database note: the admin
  can take over a member's account with a recovery link; the member would see it afterwards.

**Leaving and removing.** A member can leave at once (a recent sign-in and the word typed, like
erase): their user row is deleted and everything cascades, with no fresh start. An admin can
remove a member after telling them and offering the export. The owner's erase stays a fresh
start (ADR-0044). How leaving works and the list of left ids re-deleted after a restore are
recorded when they are built (plan step 7).

**Time.** Everyone on Europe/Berlin (`TC_TIMEZONE`). Per-person time zones only if someone
lives elsewhere.

**Legal.** Members are **training-only** until a lawyer has reviewed the privacy notice, the
consent step and a DPIA: the health categories (body measurements and photos, readiness
answers, daily checks, band data) are off for members until then. The owner is the controller,
as the legal drafts say, until the lawyer advises otherwise (the UG is an option).

**Band import** is Android-only (Health Connect, ADR-0055); iPhone members use everything else.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Invite links behind an off-by-default switch (chosen) | Same pattern as sign-in links; no email or cost; every step merges without changing anything for the owner | Whoever gets the link first joins, so it is sent privately and expires in 72 hours |
| Invite codes typed at sign-up | Easy to read out | Short codes are guessable and need rate limiting |
| Email invites | Familiar | A mail provider: spend and a new processor |
| Invites through Telegram | Telegram linked from the start | Excludes people without Telegram, which is optional |
| A starter plan or each person's own plan now | Fits people the owner's plan doesn't | A `plans` table, a plan editor, every plan query changes; not needed for the first people |

## Consequences

- ADR-0009's single allowed user no longer binds; long polling does. Until the Telegram step is
  built and the switch is on, the bot still answers only the owner, and the CLAUDE.md rule
  about `owner_only` stays true; that step changes the rule.
- ADR-0029's open point is settled: start-up never fails or moves a member over the owner's
  configured Telegram account.
- New surfaces, each with threat-model rows (`docs/security/threat-model.md`): `/join`, the
  admin page, the Telegram connect link and `/start <token>`, the admin recovery link.
- The route-access test learns a fourth kind, admin, beside public, owner and connection; admin
  answers are checked to hold counts, labels and join days only.
- Guards come before the features: an allowlist test for every cross-user lookup and a
  two-person canary over every signed-in GET route.
- Before the first invite: the notice published in the app and a DPIA written; health
  categories stay off for members until a lawyer has reviewed both.
- Build order, options and open *verify* numbers (Groq limits, database size):
  `docs/specs/multi-user-plan.md`.
