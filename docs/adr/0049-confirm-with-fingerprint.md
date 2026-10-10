# ADR-0049: Confirm it's you with your fingerprint, without signing out

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam

## Context

Some changes need a sign-in from the last 10 minutes (ADR-0040): adding or removing a passkey,
downloading or erasing everything, storing an AI key. The page said "sign in again". Doing
that meant signing out, signing in with the fingerprint, landing on Today, going back to the
Account page and doing it again. Anything typed, like a pasted key, was lost on the way. The
first time it came up (storing a Groq key), it took three tries and a question to find out why.

## Decision

Such a change now asks for the fingerprint in place and then goes ahead:

- `POST /api/auth/passkeys/confirm/options` (owner) offers only the person's own passkeys
  (`allowCredentials`, user verification required), so the phone goes straight to the
  fingerprint prompt.
- `POST /api/auth/passkeys/confirm` verifies the answer against one of their passkeys and
  sets `web_sessions.confirmed_at` on **this** session. `auth.fresh` counts the later of
  `created_at` and `confirmed_at`. There is no new session, cookie or "new sign-in" alert.
- The challenge names the person, so a sign-in challenge (no person) or another person's
  passkey can't confirm it. The sign count is checked and moved on, as at sign-in.
- The web app wraps every change that needs a fresh sign-in (`withFreshSignIn`). On a 403 it
  asks for the fingerprint once and retries. If that is cancelled, or there is no passkey,
  the page says what to do: confirm when asked, or sign in with a `/login` link.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Confirm on the current session (chosen) | One fingerprint, nothing lost, no duplicate browsers | A new endpoint pair and a column |
| Sign in again with the passkey in the background | No backend change | A second "signed-in browser", and a "new sign-in" alert every time |
| Longer fresh window or none | No friction | Weakens ADR-0040: a stolen cookie could add a passkey |

## Consequences

- The fresh window is unchanged at 10 minutes, and it still guards the same changes.
- A recovery-link session is still fresh at its start. Confirming afterwards needs a passkey,
  so a person without one signs in with a link again.
- Migration: `web_sessions.confirmed_at` (nullable).
