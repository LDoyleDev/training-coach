# ADR-0089: Telegram for members: one sender gate, and a connection confirmed on the web

- Status: Accepted (2026-11-08, Liam: a member confirms a connection on their Account page)
- Date: 2026-11-08
- Deciders: Liam (ADR-0059 and its 2026-11-07 addendum; `docs/specs/multi-user-plan.md` E and
  Decided 2026-11-07); the details here follow from a written plan and an independent review
- Changes: the root `CLAUDE.md` rule "the bot answers only `TC_TELEGRAM_ALLOWED_USER_ID`"
  (ADR-0009, ADR-0040), once built

## Context

ADR-0059 chose one bot with a private chat per person (E1): a member taps "Connect Telegram" on
Account and the bot links the sender. On 7 Nov Liam kept `/recover` for the owner and dropped a
member's link on erase. Today every handler takes the `owner_only` filter, eleven button
handlers compare the sender with `TC_TELEGRAM_ALLOWED_USER_ID` by hand, every handler class holds
one sessionmaker bound to the owner, and scheduled and ops messages go to the env id.

The review (8 Nov) checked the plan against the code and python-telegram-bot 22.8. What shaped
the decision:
- **A handler that raises in group -1 doesn't stop the update** (`ext/_application.py`): PTB
  runs the error handler and goes on to group 0. A gate that crashes would let the update
  through. The error handler gets a fresh context, so it can't see who the gate found.
- **A forwarded connect link would move the member's security alerts to whoever used it.**
  `api/alerts.alert` sends every sign-in, recovery-link and erase alert to the linked chat, so
  ADR-0059's "the member is told when a recovery link is made" would reach the wrong person. A
  Telegram first name, shown on Account, can be set to anything.
- **`auth.redeem_link` doesn't check a link's purpose**: a connect token kept in `login_links`
  could be posted to `/api/auth/redeem` and sign in a member who has no passkey.
- **Business-mode updates pass a chat check** (`chat.id == from.id`) and replies to them go out
  through the business connection.
- **Updates are handled one at a time** (PTB's default, which the bot keeps).

## Decision

**One sender gate, `bot/gate.py`, replaces `owner_only` and the away check.** A `TypeHandler` in
group -1 that catches everything and always ends in one of two ways: it sets
`context.person` (a `Person`: user id, chat, a sessionmaker bound to them, whether they're the
owner, whether health data is open to them), or it raises `ApplicationHandlerStop`. In order:
- Only `message` and `callback_query` updates, in a private chat whose id is the sender's; the
  bot also polls with `allowed_updates=["message", "callback_query"]`. Anything else stops.
- The sender is looked up in `users.telegram_user_id`. A stranger is stopped without a reply.
  With `TC_MULTI_USER` on, a stranger's `/start <token>` is the one exception (below).
- A member while `TC_MULTI_USER` is off (`users.closed_to`) is stopped without a reply; only the
  wind-down texts reach them (ADR-0059).
- Away (ADR-0085), per person: one line, except `/login` and `/recover`.
- A database error stops the update. A sender the gate has served before in this process (an
  in-memory set) is told "Something went wrong", so the owner still hears that the bot is
  having trouble; anyone else hears nothing.
- A button pressed on a message older than the person's link (`users.telegram_linked_at`) does
  nothing, so a chat relinked to someone else can't act with old buttons.

Every handler is registered through `served(...)`, which does nothing without a person and, with
`health=True` (body, readiness, daily check, band, heart rate), answers a member with one line and
writes nothing. Handler classes hold no sessionmaker: they use `me.sessions`. In-memory state
(drafts, questions asked, picks) is keyed by user id and cleared on unlink and leaving. The error
handler replies only to a person the gate recorded for that update. Scheduled and ops messages go
to the owner's chat read from the database, not the env id: after a clash the env id could name
a member. Step 9 makes the scheduled ones per person.

**Connecting is confirmed on the web.** A member taps "Connect Telegram" on Account (a recent
sign-in, `Fresh`) and gets a `t.me/<bot>?start=<token>` link: 32 random bytes, stored hashed in
its own table, `telegram_links`, never in `login_links`; once, 10 minutes, only the newest. The
bot's `/start <token>` doesn't link: it records the sender as a claim on that link and replies
with a 6-digit code, "Type this code on the Account page". Account asks for the code; the
member types the one their own Telegram shows, and Confirm (again `Fresh`) links the account
that code was sent to: it sets `telegram_user_id` and `telegram_linked_at`, records an event, and
the bot says "Connected". The Telegram name is shown only after the code matches, as a check,
never as the thing to confirm, since anyone can set any name. A link can hold several claims, so
someone who used a forwarded link first can't impersonate the member's own claim: their
code is in their chat, not the member's. At worst they force a new link (below), which fails
closed. A link takes at most 3 claims, and its codes are
unique within it (drawn again on a clash), so a code names one claim. Codes are stored hashed
with the claim and die with the link (10 minutes). Five wrong codes end the link; only the
member's own signed-in browser can type one, so someone else can't use that to end it.

What's left is persuasion: someone who used a forwarded link could send the member their own
code and say "type this to verify". So Account says, beside the code field, "Type only the code
the bot sent you after you tapped the link yourself. Never type a code someone sends you. If you
didn't open the bot just now, tap Cancel", and shows how many claims the link has. With more
than one, it says "Someone else used this link too: cancel it and make a new one", and Confirm
is off: a second claim means the link has leaked, so it is safer to start again than to pick
one. Someone who keeps seeing new links can keep forcing restarts, but never connect; the
member then asks the admin. Once a code matches, the Telegram name is shown with Confirm, as a last check. The
threat-model row for a forwarded connect link records this gap. A link that was forwarded, or seen over
someone's shoulder, does nothing without the code from the member's own Telegram typed into the
member's own signed-in browser. A Telegram account already linked to anyone is refused, as is the
owner's configured account; a member already linked must unlink first. The confirm is a
conditional update, so two at once can't both win. The connect step runs only with
`TC_MULTI_USER` on and is rate limited per sender and overall.

**Members and sign-in.** `/recover` stays the owner's (ADR-0059 addendum): a member is told to
ask the admin. `/login` for a member only points to their passkey and never sends a link, since a
member who skipped the passkey at `/join` would otherwise get a link that signs in. A member's
help text leaves out both.

**Unlink** is on Account, without `Fresh` (it only takes access away), and tells the old chat.
The owner's Account says Telegram is set on the server, with no Connect or Unlink.

## Addendum (2026-11-08): scheduled messages per person (step 9)

The morning message, the evening nudge and Sunday's review are each person's own, as the
multi-user plan's F1 has it (`bot/schedules.py`). Each person has named jobs, `morning:<user
id>`, `nudge:<user id>` and `weekly-review:<user id>` (ids are never reused, ADR-0088 addendum),
at the times in their own settings. They are made at start-up for everyone with Telegram linked
whom the switch lets in, when a member confirms a link on Account, and when that person changes
a time in /settings or on the web: the bot reads the times back from the database, so a route
only says whose. Unlink, leave, removal, erase and the wind-down take them away, on the same
path as `Gate.forget`; the owner's erase keeps the link, so theirs start again at the default
times.

Each run asks the gate whom it is for (`Gate.scheduled`): someone linked, not closed out by the
switch and not away (ADR-0085), with the chat read then, so a job left behind can't reach
anyone; a database error sends nothing. The message is built from their own bound sessions and
their own settings (paused, nudges, habits), and the morning's daily check, with the band's line,
comes only with that category open to them (ADR-0090); the owner's are unchanged.

The band, proposal and plan-notice checks stay one repeating job each, as the plan's F section
has it ("band offers loop over people with Telegram linked"), rather than one per person: each
run goes through everyone the gate would serve now (`Gate.everyone`), with that person's
sessions and chat, so one person's blocked chat or failed send doesn't hold up anyone else's.
Band offers and band data alerts go only to someone with band data open to them; a proposal
an AI has just made is sent to that person alone. Only start-up's check of the configured
account, the gate's and the connect claim's still read it (`tests/bot/test_env_id.py`); ops
alerts (backup, deploy, wind-down counts, the left list) stay the owner's, outside `bot/`.

## Consequences

- **The CLAUDE.md rule changes with the gate's PR, not at the end:** the bot serves only people
  linked in `users.telegram_user_id`, through the gate; every handler goes through `served(...)`;
  nothing in `bot/` compares a sender with the env id (a test checks); each new command and
  button is added to the bot's two-person canary.
- **Guards before features, as in the web's step 2:** the bot's two-person canary lands with the
  gate, with a member linked straight in the database and each handler class not yet converted
  marked as an expected failure, flipped in the PR that converts it. Nobody but the owner can be
  linked until the `/start` PR, and members are closed while the switch is off, so every
  intermediate state on `main` is safe.
- **Reverting:** once members are linked, reverting any conversion PR puts handlers back on the
  owner's sessions while the gate lets members through. Revert the connect PR and clear members'
  `telegram_user_id` first.
- **One at a time stays:** a member's voice note (Groq, up to 45 s) can delay the owner's next
  tap. With at most 5 members that is accepted; running handlers concurrently would need the
  in-memory state reworked first.
- **A stolen bot token** now reads members' messages too (threat model).
- Threat-model rows to rewrite with the build: the bot intro line, T1, voice, prompt injection,
  one person seeing another's data, the Telegram linking row, the invites row, "someone with the
  owner's Telegram", ADR-0085 layer 4, the bot token, erase; and a new row for a forwarded connect
  link.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| `/start <token>` links at once, the name shown on Account | One step fewer | A forwarded link silently moves the member's security alerts; the name can be faked |
| **A claim confirmed on Account with the code the bot sent** (chosen) | A forwarded link does nothing; a look-alike Telegram name can't be confirmed by mistake | Typing six digits on the web |
| A claim confirmed on Account by its Telegram name | One tap | The name can be set to anything; a first claim from a leaked link could pass as the member's (review, 8 Nov) |
| Reuse `login_links` with a new purpose | No new table | `redeem_link` takes any purpose: a connect token could sign in |
| One `Session` held per update | Simple | Holds SQLite's writer lock across Telegram and Groq calls, up to 45 s |
| Run handlers concurrently (`block=False`) | A voice note doesn't hold up others | Shared in-memory state isn't safe for it yet |
