# ADR-0040: Passkey first, Telegram for recovery, and an alert for every sign-in change

- Status: Accepted (amends ADR-0036)
- Date: 2026-10-10
- Deciders: Liam

## Context

ADR-0036 signs in with a one-time link from the bot's `/login`, then offers a passkey. Using it,
Liam noticed the link signed in without his fingerprint. Anyone holding his unlocked phone, or a
Telegram session elsewhere, could type `/login`, get in, and add **their own** passkey, keeping
access after being signed out, with nothing telling him.

## Decision

1. **Once a passkey exists, a link alone doesn't sign in.** `/login` then replies with the
   sign-in page (fingerprint) and a pointer to `/recover`, with no link token. A start link
   made before the first passkey and used after it is refused (403) and used up.
2. **`/recover`** sends a recovery link (once, 10 minutes). It signs in without a passkey,
   **signs out every other browser and removes every passkey**, so a key an intruder added can't
   survive Liam's recovery; he adds his own again. The page and the bot say so.
3. **Changing passkeys needs a fresh sign-in**: adding or removing one is allowed only within 10
   minutes of the session starting (by a link or the fingerprint). A stolen cookie can't plant a
   key. Signing a device out is always allowed.
4. **Telegram alerts** to the owner, after the response and never blocking it, for: a link
   sign-in, a passkey sign-in, a recovery, a passkey added or removed, a device signed out. They
   name the browser as it describes itself (plain text, no formatting). With the bot off only
   the log line (`auth.alert`, kind only) remains.
5. **The bot answers only in its private chat with the owner** (from the security review): in a
   group, a recovery link or a log would be seen by everyone in it.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Passkey first, Telegram recovery with alerts (chosen) | A lost phone is recoverable; a Telegram takeover can't be silent | Whoever holds Telegram can still recover, but loudly |
| No recovery outside the Pi | Strongest | A lost phone means SSH to the Pi to get back in |
| Keep link sign-in | Simplest | Silent takeover and passkey planting (the reason for this ADR) |

## Consequences

- For a public, multi-user app, Telegram-only recovery is too weak: a second factor or a delay
  with alerts is needed then (security review). Absolute session expiry, `__Host-` cookies and
  an Origin check are tracked from the same review.
