# Invite-only multi-user (L2): a plan with options

Status: **decided 2026-10-12**: the owner answered every question (below, under Decided), and
[ADR-0059](../adr/0059-invites-and-members.md) records the decisions. Written 2026-10-12 from an
audit of the code on `main` at 0.27.0. It builds on L2 in
[platform-and-health-data-proposal.md](platform-and-health-data-proposal.md) and the direction
in [ADR-0026](../adr/0026-multi-user-direction.md): built for the owner first, public in the end,
Android first, zero spend, a fitness app and not a medical one, GDPR and Germany. Numbers marked
*verify* are not checked against the provider today.

## Decided (2026-10-12)

The owner's answers to the 16 questions this plan asked; all as recommended except 7. The
options they choose between are below.

1. **When:** build steps 1-3 (guards and fixes) now; the rest when there is a first person in mind.
2. **How many:** at most 5 members (`TC_MAX_MEMBERS`), adults only; raise it later.
3. **Invites:** a one-time link (A1), valid 72 hours, revocable, with an optional label.
4. **Who can invite:** admins only.
5. **Roles:** a role column (B1); the owner is the only admin.
6. **What the owner sees:** counts, plus each member's label and join day, nothing of their data
   (C1); no "last active".
7. **Plans:** D1 to start: everyone on the owner's plan with their own progress. **Each person
   having their own plan** (a D3-style copy they can change) is the goal for later, not built
   now. Until then, new code takes the person's plan where it can as cheaply as assuming one
   global plan, so the later change is not made harder.
8. **Telegram:** optional for members, one bot, linked from Account (E1); members without
   Telegram get no reminders until Web Push.
9. **Voice:** the app's Groq key with a cap of 20 a day per member (H1); AI comments on each
   person's own key, as now.
10. **Recovery:** an admin-issued recovery link, plus `/recover` for members with Telegram (I1).
11. **Leaving:** a member can leave at once, erasing everything; the owner can remove a member
    after telling them and offering the export.
12. **Switching back off:** with members still there, tell them, keep their data 30 days for
    export, then erase it.
13. **Time zone:** Europe/Berlin for everyone; per-person time zones only if someone lives
    elsewhere.
14. **Legal:** no one else's health data before a lawyer has reviewed the notice, consent and
    DPIA. Members start training-only: the health categories (body, readiness, daily check,
    band) are off for members until then.
15. **Controller:** the owner personally, as the legal drafts say, until the lawyer advises.
16. **iPhone members:** band import is Android-only; that is fine.

## What's true today

### The data is already scoped

- `User` (`backend/src/training_coach/db/models.py`) has only `id`, `telegram_user_id` (unique)
  and `created_at`. No role, no name, no consent record. User 1 is the owner
  (`services/users.py`, `OWNER = 1`), made by the migration that added users.
- **24 per-person tables** inherit `Owned` and carry `user_id` with `ON DELETE CASCADE`:
  workouts, set_logs, exercise_state, plan_state, settings, events (empty for system events),
  habit_checks, test_days, measurements, progress_photos, session_progress, login_links,
  web_sessions, passkeys, readiness_answers, daily_checks, ingest_keys, health_days,
  heart_rate_samples, sleep_sessions, imported_workouts, ai_connections, ai_comments,
  mcp_connections. `tests/db/test_user_scope.py::test_every_per_person_table_is_covered` pins
  the list.
- **Shared, not `Owned`:** the plan (exercises, ladder_steps, plan_versions,
  session_templates, template_items), passkey_challenges (a sign-in belongs to nobody yet),
  and the OAuth tables. oauth_clients belong to nobody; oauth_codes and oauth_tokens reach a
  person only through their `mcp_connections` row; oauth_consents carries its own nullable
  `user_id` (and `web_session_id`), set once the person proves their passkey on the consent
  page, with `ON DELETE CASCADE` but outside the run-time binding.
- **Scoping is enforced at run time, not by hand** (ADR-0029, `db/session.py`). A session made
  with `make_session_factory(engine, user_id=...)` adds `user_id == user` to every select and
  delete on every owned model, stamps new rows, and refuses writing another user's row, a set on
  another's workout, a change of owner, and bulk inserts or updates. An unbound session refuses
  to touch owned tables unless the statement passes `all_users`.
- **Every web route already works for whoever is signed in.** The `owner` dependency
  (`api/auth.py`) returns the signed-in user's id from the session cookie, and each router binds
  its sessions to that id. Export (`services/export.py`), erase (`services/erase.py`), passkeys,
  the band ingest secret (`services/ingest_keys.py`, one per person, looked up by hash), the
  person's own Groq key (`ai_connections`, encrypted with `TC_SECRETS_KEY`) and MCP connections
  are all per person already.
- **Cross-user lookups, all deliberate:** `ALL_USERS` is used in `services/auth.py`,
  `services/passkeys.py`, `services/mcp_tokens.py`, `services/ingest_keys.py` (whose token is
  this?), `services/seed.py` (provisioning and "is this step in use") and
  `services/ai_key.py::rotate_all`. Unbound `shared_sessions` are read in `api/auth.py`,
  `api/passkeys.py`, `api/oauth.py`, `api/ingest.py` and `api/mcp.py`.

### Where the code still assumes one owner

| Where | What it assumes | What L2 needs |
| --- | --- | --- |
| `config.py`: `telegram_allowed_user_id`, `bot_enabled` | One Telegram account; the bot runs only when it is set | Kept as the owner's bootstrap; members are linked in the database |
| `bot/app.py::owner_only` | A fixed `filters.User(user_id=...)` on every command, text and voice handler | A filter backed by the linked accounts in `users` |
| Sender checks in button and error handlers: `bot/app.py` (2), `band.py`, `daily_check.py`, `habits.py`, `logging_flow.py`, `progress.py`, `settings.py`, `stretching.py`, `undo.py` | Each compares the sender with `telegram_allowed_user_id` | Find the user by the sender's Telegram id |
| `api/app.py` lifespan, `users.link_owner` | The bot gets **one** sessionmaker bound to the owner at start-up; every handler class holds it | A session bound per update, to whoever sent it |
| `bot/app.py::schedule_jobs` | One `morning`, `nudge` and `weekly-review` job, from the owner's settings, sent to `telegram_allowed_user_id` | Jobs per person, sent to that person's chat |
| `bot/band.py::announce` | Band workouts are offered to the owner's chat only | Loop over people with Telegram linked |
| `services/erase.py` | Erase means a fresh start under the same id and Telegram link (ADR-0044) | Members can also leave: delete without recreating (ADR-0044 expects a successor) |
| `services/users.py::link_owner` | Moves the owner to whatever Telegram id is configured; a member holding that id would make start-up fail on the unique constraint (ADR-0029 says the invites ADR must settle it) | Bootstrap only; never take a member's link |
| `seed/plan.toml`, `session_templates.position` and `.slug` unique | One plan for everyone; each person has their own place in it and their own ladder steps | See D |
| `config.py::timezone` (`settings.tz`, 68 uses in 27 files) | Everyone lives in Europe/Berlin | Fine for Germany; per person is a bigger change |
| `config.py::groq_api_key` | The app's Groq key transcribes and reads logs for whoever uses the bot; no per-person cap | A per-person daily cap |
| `services/backup.py`, `scripts/offsite-backup.sh` | One database, everyone in it | Restoring brings back people who left (see J) |
| `__main__.py::notify`, the heartbeat, deploy alerts | Ops messages go to the owner | Unchanged: the owner runs the Pi |

Fixed in step 3 (#236): alerts go to the person they are about, and only ops alerts go to the
owner; changing message times on the web moves the bot's jobs only when the owner changes them
(jobs per person come with step 9); Telegram drafts are kept and capped per sender.

### How sign-in works now (ADR-0036, ADR-0040)

- **First sign-in:** `/login` in the bot sends a one-time link (32 random bytes, stored as
  SHA-256, single use, 10 minutes, token in the URL fragment). It starts a web session; the
  person then adds a passkey.
- **After that:** passkey only (fingerprint or face). A start link no longer signs in on its own.
- **Recovery:** `/recover` in the bot signs in, signs out every other browser, removes every
  passkey and alerts. ADR-0040 already says Telegram-only recovery is too weak for a public app.
- **Gap for L2:** the only way to a first session is the bot, and the bot answers only the
  owner. A new person needs another way in: the invite.

### Tests that guard it

- `tests/db/test_user_scope.py`: two users, each sees and changes only their own rows (reads,
  joins, `session.get`, cached statements, bulk deletes, refused writes, the unbound guard), and
  no shared model links to an owned one.
- `tests/api/test_auth.py::test_every_route_is_public_or_owner_only`: every route is listed as
  public, or depends on `owner` (cookie), or on `connection` (MCP), never two.
- `tests/test_architecture.py` and the import-linter contracts in `backend/pyproject.toml`:
  adapters hold no models or query builders.
- **Not covered:** a new `ALL_USERS` or unbound session added somewhere it shouldn't be; a route
  that binds to the wrong user; the bot handling one person's update with another's session.
  These are the likely L2 bugs (see L).

### Legal pieces already drafted (docs/legal/)

- `privacy-policy.md` (draft): what is stored, health data on explicit consent (Art. 9(2)(a))
  for measurements and photos, readiness answers, daily checks, band data and the AI comment;
  processors (Telegram, Groq in the USA, Cloudflare, Healthchecks.io); 5-week backup age-out;
  rights; export and erase on Account. Names Liam as responsible.
- `README.md`: both texts are needed **before anyone else signs in**; open items are the
  controller (the UG), a postal address, a German version, consent wording in sign-up,
  per-category erase when consent is withdrawn, and Art. 28 processing agreements; a lawyer
  review is deferred to launch.
- `impressum.md`: not needed while the site is a personal tool (ADR-0041).
- **What L2 adds:** a consent step per data category with a record of it, the notice shown and
  accepted before sign-up, per-category withdrawal and erase, leaving, a DPIA (the proposal
  notes German regulators treat health apps as high-risk processing), and the owner as
  controller of other people's health data. Whether that is still a personal tool for the
  Impressum, and which of these are strictly required for a handful of invited people, is for a
  lawyer; this plan does not decide it.

### Resources for "a handful of people"

- **Pi 5, 8 GB** (ADR-0002), shared with Vybe; the app container is capped at **512 MB**
  (`compose.yaml`). One process, SQLite in WAL mode on an SD card (ADR-0010). Five people
  logging a few times a day is far below what SQLite handles; the heaviest per-person writes
  are band syncs (minute heart rate, kept 8 days: about 11,500 rows per person).
- **Export** builds the zip in memory (`services/export.py`): a few MB per person.
- **Off-site backups:** 35 nightly copies on Cloudflare R2's free 10 GB (ADR-0042). Photos
  (about 300 KB each) dominate the database size, so each person's photos count about 35 times
  off-site. Check the real database size on the Pi before inviting (*verify*).
- **Groq free tier** for the app's own key: 2,000 transcriptions and 28,800 audio seconds a day
  (ADR-0008, *verify*). Voice notes are capped at 2 minutes (`bot/logging_flow.py`), so at worst
  240 long notes a day for everyone; five people at four notes a day use 20. The parse model's
  daily limits are not recorded anywhere (*verify*). Whether Groq's free tier terms allow
  processing other people's data is also *verify*. AI comments already use each person's own
  key (ADR-0047 B).
- **Telegram:** one bot sends to many chats; the limits (about 30 messages a second overall, 1 a
  second per chat, *verify*) don't matter at this size.
- **Per-address limits:** passkey sign-in allows 5 open challenges per address, band ingest 60
  calls and 10 wrong secrets per 10 minutes per address. A family on one home connection shares
  an address; likely fine for a handful, worth a test.

## Options

### A. Invites

| Option | What | Pros | Cons |
| --- | --- | --- | --- |
| A1 **One-time link** (recommended) | The owner makes an invite on Account; it shows a link (and a QR code) to send by any messenger. `/join#token`: 32 random bytes, stored as SHA-256, single use, expires | Same pattern as sign-in links; no email, no cost; works without Telegram | Whoever gets the link first joins, so it is sent privately and expires soon |
| A2 Invite code typed at sign-up | A short code instead of a link | Easy to read out | Short codes are guessable; needs rate limiting |
| A3 Email invite | The app emails the link | Familiar | Needs a mail provider (spend, a new processor) |
| A4 Invite through Telegram | The person messages the bot with a code | Telegram linked from the start | Excludes people without Telegram; Telegram is optional (proposal, section 0) |

Details for A1: expiry 72 hours; the owner can see and revoke open invites; an optional label
("Mum") so the owner's list makes sense; at most `TC_MAX_MEMBERS` people. Redeeming shows the
privacy notice and the consent step (M), checks the person is an adult, creates the user and
their starting rows (as the seed does), starts a web session and asks for a passkey straight
away. An `invites` table is shared (not `Owned`): it names who made it and, once used, who it
became.

**Who can invite:** only admins (recommended), or any member (grows on its own; the owner loses
track of who holds health data they control).

### B. Roles

| Option | What |
| --- | --- |
| B1 **A `role` column, admin or member** (recommended) | The owner is admin. An `Admin` dependency on top of `owner`; the route test learns a fourth kind (public, owner, admin, connection) |
| B2 "User 1 is admin" | No schema change, but a hidden rule that breaks the day a second admin is wanted |

Admins can: make and revoke invites, see counts (C), remove a member, issue a recovery link,
and get ops alerts. Admins can't: read or change a member's data.

### C. What the owner sees of other people

| Option | What |
| --- | --- |
| C1 **Counts only** (recommended) | Number of members, open invites; per member only the label you gave and the day they joined, so you can remove the right person. Nothing of their training, body, health or band data |
| C2 Plus "last active" | Helps spot unused accounts, but is a fact about their behaviour |
| C3 A coach view | See their sessions to help them. Needs their consent per person, and makes you a coach with access to health data: a different product |

Say plainly in the privacy notice that whoever runs the Pi can technically read the database and
backups; the app offers no way to do it, and nobody does.

### D. Plans per person

What exists: one plan from `plan.toml`, shared. Each person already has their own place in the
queue (`plan_state`), their own ladder step per exercise (`exercise_state`), their own settings,
tests and blocks. 31 of 32 exercises start at the easiest step.

| Option | What | Pros | Cons |
| --- | --- | --- | --- |
| D1 **Everyone on your plan, own progress** (recommended) | New people start at the plan's starting steps; baseline tests (ADR-0037) and progression move them on | Works today; no schema change | Huberman's 7-day cycle may be too much for some people; the queue (ADR-0006) and Rest today soften it |
| D2 A starter plan or a picker | A second bundled plan (say 3 days a week); each person picks one | Fits beginners | A `plans` table and `plan_id` on sessions and versions; `position` and `slug` stop being unique; seed loads several files. Medium to large |
| D3 Each person's own copy of `plan.toml` | Copy yours, then edit | Most flexible | Needs a plan editor and per-person plan tables; every plan query changes. Large; more L3 |

Decided (7): D1 to start; each person's own plan, D3-style, is the goal for later.
Planned in [program-builder.md](program-builder.md) (draft, 2026-10-21), which proposes building
it now for the owner alone, ahead of the other multi-user steps.

### E. Telegram for members

| Option | What | Pros | Cons |
| --- | --- | --- | --- |
| E1 **One bot, many private chats** (recommended) | The person taps "Connect Telegram" on Account: a one-time token (hashed, 10 minutes) in a `t.me/<bot>?start=<token>` link; the bot's `/start <token>` links their account. The bot then finds the user from the sender for every update and uses a session bound to them | One bot, one token; same features for everyone | `owner_only` and 10 sender checks change; every handler gets its session per update |
| E2 Telegram for the owner only | Members use the web app only | Smallest change | No reminders for members until Web Push exists (not built) |
| E3 A bot per person | | | More tokens, more processes; no |

With E1: `/start <token>` is the only thing a stranger can reach, and only with a live token
(rate limited). Private chats only, as today. `TC_TELEGRAM_ALLOWED_USER_ID` stays as the owner's
first link; after that a conflict with a member's link logs an error and keeps the existing link
rather than failing start-up (settles ADR-0029's open point). Unlinking is on Account; erase
removes the link.

### F. Messages and schedules per person

| Option | What |
| --- | --- |
| F1 **Named jobs per person** (recommended) | `morning:<user>`, `nudge:<user>`, `weekly-review:<user>` from each person's settings, made at start-up for everyone with Telegram linked and moved when they change their times. Smallest change from today's code; DST handled the same way |
| F2 One job every minute | Sends whatever is due for anyone. Scales further, but changes how every message is timed |

Band offers loop over people with Telegram linked. The weekly AI comment stays on each person's
own key (ADR-0047 B). Members without Telegram get no reminders until Web Push (proposal, L1).

### G. Band data per person

Already per person: each person makes their own ingest secret on Account (ADR-0055), stored
hashed, and the endpoint finds the user by it. L2 needs only the consent step for band data
(M) and a runbook line for setting up a member's phone. Band import needs Android (Health
Connect); iPhone members can use everything else.

### H. The app's Groq key

| Option | What |
| --- | --- |
| H1 **The app's key for everyone, capped per person** (recommended) | Voice and fallback parsing as today, with a daily cap per person (say 20) so one person can't use up the day for everyone; above it, "type it instead" |
| H2 Members bring their own key for voice too | No shared quota; extra setup for every member |
| H3 Voice off for members | Simplest; loses a main feature |

Members' voice notes then go to Groq in the USA on your key: the privacy notice already lists
it, but the transfer and processing agreement are open items there.

### I. Recovery for members

ADR-0040: Telegram-only recovery is too weak for a public app. For a handful of people you know:

| Option | What |
| --- | --- |
| I1 **An admin-issued recovery link, plus `/recover` if they linked Telegram** (recommended) | You make a recovery link for them (single use, 24 hours, same rules as `/recover`: signs out other browsers, removes passkeys, alerts them) and send it the way you sent the invite |
| I2 Printed recovery codes | Works without you; more to build, and codes get lost |
| I3 Telegram only | Leaves people without Telegram locked out |

### J. Leaving and removing

- **Leave** (member, on Account, needs a recent sign-in and the word typed, like erase): delete
  the user row; the cascade removes everything, Telegram link included; no fresh start. Backups
  age out within 5 weeks, as the privacy notice says.
- **Remove a member** (admin): the same, after telling them; offer them the export first.
- **Owner's erase** stays a fresh start (ADR-0044).
- **Restoring a backup** would bring back people who left. Keep a list of left user ids (ids
  only) and re-delete them after any restore; add it to `docs/runbooks/backup-restore.md`.
- An ADR succeeding ADR-0044 records this.

### K. Staying single-user (kill switch)

`TC_MULTI_USER`, **off by default**, so every L2 PR can merge without changing anything for you.

- Off: invites can't be made or redeemed; the admin page shows nothing; only the owner can sign
  in or use the bot; only the owner's jobs run. Members' data is kept, untouched.
- On: the above opens up, to at most `TC_MAX_MEMBERS` people.
- Turning it off with members still there: they are locked out but not erased, then erased
  after 30 days (Decided, 12).
- A test runs the whole app with the flag off and a member in the database, and proves the
  member can't sign in, link Telegram or get messages.

### L. Enforcing "every query is scoped"

The run-time binding (ADR-0029) already makes a forgotten filter safe. What can still go wrong
is the session itself: unbound where it shouldn't be, or bound to the wrong person. Proposed
guards, cheapest first:

1. **An allowlist test for cross-user access** (recommended, first). An AST walk over `src/`
   finds every use of `ALL_USERS`/`EVERYONE`, every `make_session_factory(...)` without
   `user_id=`, every read of `app.state.shared_sessions`, and any `.connection()` or `text(`.
   Each must match an entry (`module::function`, with a reason) in the test; a new one fails
   until reviewed, like `test_every_route_is_public_or_owner_only`. An import-linter contract
   could do part of this if `ALL_USERS` moved to its own module that only listed services may
   import.
2. **A two-person canary test** (recommended). User A gets distinctive values (a measurement of
   123.4, a workout on a marked day, a photo, a band night). Signed in as B, call every GET route
   behind `owner`, enumerated from `app.routes` (path parameters from a small table; a route
   missing from it fails the test). None of A's values may appear; B's own must. New routes are
   covered without anyone remembering to.
3. **Route access learns `admin`**, and admin responses are checked to hold counts only.
4. **Bot:** two linked members; each sees only their own `/today`, logs, buttons and drafts; a
   press carrying the other's draft token is refused; each scheduled message goes to its own
   person's chat with their own data.

### M. Consent, notice, DPIA

- **Consent per category**, matching the privacy draft's health rows: body (measurements and
  photos), readiness answers, daily check, band data, and what the AI comment may see (already
  the `share_body` and `share_readiness` switches). A `consents` table (per person: category,
  notice version, given, withdrawn). A feature asks for its consent the first time it is opened;
  withdrawing erases that category (the privacy draft lists this as needed before launch).
  Training data (workouts, sets) runs on the contract, as the draft says.
- **Privacy notice** shown and accepted when redeeming an invite, and as a page in the app;
  a new version is shown before it applies.
- **DPIA**, a short one, in `docs/legal/` before the first invite.
- **Adults only** at sign-up.
- **Fitness, not medical:** the readiness questions (ADR-0046) already send people to a doctor
  before hard efforts; keep advice to "as planned, lighter, rest".
- **For a lawyer**, not decided here: whether the household exemption could apply; whether a
  DPIA is mandatory at this size; whether the Impressum is needed for an invite-only site; who
  the controller is (you or the UG); processing agreements and the US transfer for Groq and
  Cloudflare; consent wording in German.

## Suggested order (small PRs, all behind `TC_MULTI_USER` off)

1. **Done (#233, ADR-0059).** **ADR** for invites and members (supersedes ADR-0009's single
   allowed user; settles ADR-0029's relink point), and threat-model rows for invites, linking
   and admin.
2. **Done (#235).** **Guards first:** the cross-user allowlist test and the two-person canary
   test (L1, L2). Tests only.
3. **Done (#236).** **Fix the owner leaks** that don't need a second person to fix: alerts to
   the person they're about, settings moving only that person's jobs, drafts per person.
4. `users.role` and `label`, `TC_MULTI_USER` and `TC_MAX_MEMBERS`, the `Admin` dependency and
   the route test's fourth kind.
5. **Invites:** table, make and revoke on Account ("People"), `/join` with notice, adult check
   and passkey.
6. **Consent records** and per-category withdraw and erase.
7. **Leave, remove a member, admin recovery link** (ADR succeeding ADR-0044) and the restore
   runbook step.
8. **Telegram for members:** connect link, the members filter, a session per update.
9. **Schedules per person**, and band offers and band data alerts per person (the alert
   state is already per person, on `ingest_keys`).
10. **Groq cap per person.**
11. **Legal before the first invite:** notice published in the app, DPIA written, then
    `TC_MULTI_USER` on. Members stay training-only until a lawyer has reviewed the notice,
    consent and DPIA (Decided, 14).

Steps 1-3 are worth doing even if L2 waits: they make the single-user app safer and cost little.

## Questions

All 16 questions were answered on 2026-10-12; the answers are under Decided, at the top. The
questions as asked are in the history of this file (#230).
