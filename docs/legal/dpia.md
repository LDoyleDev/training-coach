# Data protection impact assessment (draft)

> Draft, not published and not legal advice. A short assessment of the private test with invited
> family and friends (ADR-0090), written before the first invite as ADR-0059 and ADR-0090 ask.
> The lawyer reviews it before anyone outside that group joins. Items in [brackets] are open.
> Written from how the app works on 2026-11-08.

Facts live in their own documents, and this one points to them: what is stored, why and on what
basis in the [privacy notice draft](privacy-policy.md); controls and their tests in the
[threat model](../security/threat-model.md) and the
[MCP threat model](../security/mcp-threat-model.md).

## Why an assessment

Training Coach processes health data (Art. 9 GDPR) of people other than the person running it:
body measurements and progress photos, daily checks, and band data such as heart rate and sleep.
German authorities treat health apps as processing that needs one (Art. 35(4)) [lawyer: confirm
against the authorities' list]. Whether one
is required at this size (at most 5 members) is a question for the lawyer; it is written anyway.

## 1. The processing (Art. 35(7)(a))

- **Who:** the owner (Liam) and at most `TC_MAX_MEMBERS` (5) invited adults living in the EU or
  EEA. No public sign-up; only the admin makes invites (single use, 72 hours, revocable), and
  nobody can join while `TC_MULTI_USER` is off, its default (ADR-0059).
- **What and why:** a training plan, the workouts logged against it and the progress made, on the
  contract; and, for each person who says yes to that category, health data that shows progress
  and advises how hard to train that day. The categories and what each opens are in ADR-0090's
  table; the rows, purposes and legal bases are in the privacy notice draft.
- **Not processed on the server:** the health questions' answers are worked out on the device and
  never sent (ADR-0085). Voice notes are transcribed and discarded, never written to disk.
- **Where:** one server run by the controller [in Germany], on a Raspberry Pi; Telegram, Groq,
  Cloudflare and Healthchecks.io as listed in the privacy notice draft.
- **How long:** until the person erases it, withdraws that category or leaves; backups age out
  within 5 weeks (ADR-0042, ADR-0044). Per-minute heart rate is kept 8 days, daily checks a year,
  the weekly AI comment 7 days.

## 2. Necessity and proportionality (Art. 35(7)(b))

- **Each health category is optional.** Training works with none of them, and each is asked for
  the first time its feature is opened, with its own wording and version (ADR-0090). A no leaves
  that feature closed and nothing else.
- **Withdrawing erases.** Withdrawing a category on Account deletes its data at once and closes
  it again; the record of the consent itself stays until the person leaves or erases everything.
- **Minimal by design:** no analytics, tracking or adverts; one strictly necessary cookie; photos
  stripped of metadata; only "last seen in Europe" kept, never an IP address for it (ADR-0085).
- **The person's rights in the app:** download everything, erase everything, leave, withdraw a
  category (privacy notice draft, "Your rights").
- **The coach suggests, the person decides:** advice stays "as planned, lighter, rest", and the
  health questions send people to a doctor before hard efforts. Nothing changes a plan without a
  tap.

## 3. Risks to the people (Art. 35(7)(c))

| Risk | Likelihood before controls | Harm |
| --- | --- | --- |
| R1: one person sees or changes another's data, through the web, the bot, an AI app or a bug | Medium: one database holds everyone | High: health data and photos of family and friends |
| R2: health data kept or used without a yes, or after withdrawal | Medium | High: no lawful basis (Art. 9) |
| R3: someone joins or signs in who wasn't invited, or takes over a member's account | Low: invite only, passkeys | High |
| R4: a stranger links their Telegram to a member, or a member's chat gets another's messages | Low | Medium to high: training and some health data on Telegram |
| R5: data leaves through a service (Groq, Cloudflare, Telegram) or a transfer to the USA | Medium | Medium: voice notes and log text go to Groq; traffic passes Cloudflare |
| R6: the owner (as admin) reads a member's data | Medium: he runs the server | Medium: trust between family and friends |
| R7: data lost (the SD card, a bad release) or kept longer than said (backups) | Medium | Medium |
| R8: advice taken as medical advice; someone hurt training | Low to medium | High for the person |

## 4. Measures (Art. 35(7)(d))

- **R1:** every per-person table is read and written through a session bound to that person
  (ADR-0029), so another's rows can't be read or changed by mistake; a cross-user test allowlists
  every query that reads across people, and a two-person canary covers the API. [Open: the bot's
  canary comes with the per-person bot, R4.]
  Threat model: "One person seeing or changing another's data".
- **R2:** each category opens only on a yes to its current wording, checked on every health
  route, MCP scope, proposal and band post; a 403 names the category; an append-only record shows
  each yes and withdrawal with the wording version (ADR-0090). Threat model rows for ADR-0090.
  [Open: the walk-through's answers have their category in the record, but the walk-through isn't
  built, so there is nothing yet for its withdrawal to erase.]
- **R3:** invites as in section 1; passkeys with user verification; sign-in links single use,
  10 minutes, hashed; every sign-in and passkey change alerted (ADR-0036, ADR-0040, ADR-0059).
- **R4:** the sender gate stops every Telegram update not from a linked person in their own
  private chat, failing closed; linking is confirmed on the website with a code from the bot
  (ADR-0089). [Open: the per-person bot and the connect step are being built; until they are,
  members can't use the bot, and the switch stays off.]
- **R5:** voice is off until the person's key is set; voice notes held in memory only; Groq gets
  no tools and its output is checked and confirmed (ADR-0007, ADR-0023); backups encrypted before
  they leave the server. [Open: data processing agreements and the US transfer basis for Groq and
  Cloudflare; Telegram's entity.]
- **R6:** admin pages show counts, labels and join days only, never a member's data (ADR-0059).
  The owner also holds the server and its backups: that can't be technically excluded on a
  self-hosted server, so the notice and the invite should say it plainly. [Open: wording.]
- **R7:** nightly backups, an encrypted off-site copy and restore drills; releases that change
  data get a backup and a dry run on a copy first; backups deleted within 5 weeks (ADR-0042,
  ADR-0044).
- **R8:** fitness, not medical: the health questions (ADR-0085) and the "as planned, lighter,
  rest" advice; no HIIT, jumps or heavy loading in the starters; a clinician checks the health
  wording before the public release (#556).

## 5. Outcome

With the measures above, and while the group stays invited family and friends behind the
switch, the remaining risk is judged acceptable for a private test, with no need to consult the
authority (Art. 36) [lawyer: confirm]. Before the first invite: the open items in R2 and R4 are
built, the notice is shown in the app (plan step 11), and R6's wording is in the invite. Before
the public release: the lawyer's review of this assessment, the notice, the consent wording and
who the controller is (Liam or the UG).

Review this assessment when a category, service or surface is added, and before the switch is
first turned on.
