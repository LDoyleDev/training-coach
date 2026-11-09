# ADR-0090: Consent per category, and a private test with invited family and friends first

- Status: Accepted
- Date: 2026-11-08
- Deciders: Liam (8 Nov 2026, in chat; `docs/specs/multi-user-plan.md` Decided 2026-11-08); the
  record, categories and withdrawal follow `multi-user-plan.md` M and the privacy draft
- Changes: ADR-0059's "Legal" paragraph (members training-only until a lawyer's review) and
  `multi-user-plan.md` Decided 14 and step 11

## Context

ADR-0059 kept members training-only until a lawyer had reviewed the privacy notice, the consent
step and a DPIA: `users.health_open` is the owner only, by id, and every health route answers a
member 403 (`api.auth.Health`). On 7 Nov Liam asked for the consent step to be built now, at the
start of the walk-through, per category, with a record of each.

On 8 Nov he set the order: the app starts with family and friends only, so the lawyer's review
comes before any outside guests or customers, not before them. What it needs now is to be done
correctly, and controlled so that nobody else can get in or use it until a public release. He
chose to open each health category for a member who gives consent to it, and to keep the
existing controls, with the joining page and the notice saying it is a private test.

The privacy draft already names the basis for each kind of data: training on the contract
(Art. 6(1)(b)), and body measurements and photos, daily checks and band data on explicit consent
(Art. 9(2)(a)), withdrawable at any time.

## Decision

**Two stages.**
- **Private test (now):** invited family and friends. Only an admin makes invites (single use,
  72 hours, revocable); joining needs `TC_MULTI_USER` on, at most `TC_MAX_MEMBERS` (5) people
  besides the owner, adults only, the EU and EEA only. There is no public sign-up anywhere. The
  join page and the notice say "a private test for invited family and friends". Turning the
  switch on stays Liam's call.
- **Public release (later):** only after a lawyer has reviewed the notice, the consent wording,
  the DPIA and who the controller is, and a clinician has checked the health wording (#556's
  lists). Until then the app takes no one it wasn't invited to take.

**Consent per category.** Four categories, each matching a row of the privacy draft:

| Category | What it opens | Data a withdrawal erases |
| --- | --- | --- |
| `body` | Measurements (resting heart rate typed in too), photos, body settings | `measurements`, `progress_photos` and their files |
| `daily_check` | The daily check | `daily_checks` |
| `band` | Band import and its data, heart rate on cardio, heart-rate settings | `health_days`, `heart_rate_samples`, `sleep_sessions`, `imported_workouts`, `band_feeds`, the phone's key; cardio heart rates and the max heart rate set to empty |
| `walkthrough` | The walk-through's answers (age, how you exercise now, what you can do, days, minutes, kit; narrowed in the 9 Nov addendum) | Those answers; the plan made from them stays |

The safety questions' answers never reach the server (ADR-0085), so they need no consent.
Training data (workouts, sets, the plan) runs on the contract.

**The owner** is the controller of their own data and isn't asked: their categories are always
open, as now.

**The record.** A `consents` table, per person and append-only: category, the wording version
shown, `given` or `withdrawn`, and when. The latest row per category is the current answer, and
the history is what shows consent was given. A category's wording has a version in the code;
when it changes, the person is asked again before that category is used. The export includes the
records; leaving or erasing deletes them with everything else.

**Where it's asked.** A feature asks for its category the first time it's opened, with the draft
wording, "Yes" and "Not now". The walk-through asks for `walkthrough` at its start. Without
consent, the routes for that category answer a member 403 with `consent_needed` and the
category, so the web shows the consent card instead of an error. "Not now" leaves it closed and
asks again only when the person opens the feature again.

**Withdrawing** is on Account, beside each category, as easy as giving it, and erases that
category's data at once. It is the person's own data going away, so it asks for a recent
sign-in (`Fresh`) and a confirm that says what will be deleted. The backups age out within five
weeks, as the notice says.

**Elsewhere.** A member's AI app gets the body scope only with `body`, and the readiness scope
(daily checks) only with `daily_check`. Its body or heart-rate proposals are refused without
`body` or `band`. The phone's band posts are refused without `band`, as now without counting as
a wrong secret. The AI comment sees health data only with both the category and the existing
`share_body` or `share_readiness` switch. `/share` still never shows any of it (ADR-0050).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| **Consent per category, members open on consent, lawyer before outsiders** (chosen) | Family and friends get the whole app; each category is a clear yes with a record; withdrawal really erases | The notice and wording are drafts while real people's health data is kept; the owner carries that for a handful of invited people |
| Members training-only until the lawyer (ADR-0059 as it was) | Nothing to get wrong before the review | Family and friends can't use body, daily checks or the band; the consent step would sit unused |
| One consent for all health data | One question | Not specific, as Art. 9(2)(a) and Art. 7 need; withdrawing one thing would mean losing all |
| Consent as a column on each feature's settings | No new table | No history: nothing shows when consent was given or to which wording |

## Consequences

- `users.health_open(user_id)` becomes per category: the owner by id, or a member whose latest
  record for that category is `given` at the current wording version. `api.auth.Health` takes the
  category; `tests/api/test_training_only.py` becomes a test that every health route names one
  and answers a member without consent 403.
- Build order, each safe on `main` since members are closed while the switch is off: this ADR
  and the plan; the `consents` table, service and routes, with withdrawal erasing; the health
  routes, MCP scopes, proposals and band posts per category; the consent card and Account's
  list on the web; the "private test" wording on joining and in the notice.
- Before the first invite: the notice shown in the app (step 11) and a short DPIA in
  `docs/legal/`, both drafts; the lawyer's review moves to before the public release.
- Threat-model rows: a member's health data kept without consent, or after withdrawal; the
  training-only row is rewritten.
- `docs/legal/README.md` and the privacy draft say the consent step exists and what the private
  test is.

## Addendum (9 Nov 2026): what the walk-through's category holds (ADR-0092)

The table's `walkthrough` row listed "days, minutes, kit". Minutes, kit and places are ordinary
settings, kept on Account without consent as training data, so the walk-through writes them there
and they stay on withdrawal, like the plan (ADR-0092, Decided 2). The category holds the
walk-through's own answers: the age band, how they exercise now (how often, how hard, how long),
the four everyday answers, the tapped days and the "can you do...?" answers. They are kept in
`walkthrough_answers`, one row per person, and withdrawing deletes the row; the plan, the levels
and the settings made from them stay. The consent wording says so and goes to version 2; nobody
had given version 1.
