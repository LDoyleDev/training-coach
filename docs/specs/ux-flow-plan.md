# Making the app flow: a UX plan with options

Status: **proposal, for review** (written 2026-10-11, from a read of every page and bot flow
done the evening before). Part 1 is being built now because it was asked for directly; the
rest waits for a decision.

## What's wrong today

- **Buttons don't look like buttons.** The global CSS has no button or input styles, so many
  actions render as plain text: Sign out, Add/Remove passkey, Download, Erase, Copy for my AI,
  Check and save the key, and Sign in with fingerprint. Several inputs have no border at all,
  so the Groq key field was close to invisible.
- **Sizes are off.** The h1/h2 rules override the Tailwind sizes, so every section title is
  about 32px on a phone, including small card titles. One-line notes get 64px gaps.
- **The nav overflows on a phone.** Seven items in one row, no wrapping, and tap targets about
  26px tall. `/plan` drops the nav entirely, and its text still says "everything happens in
  Telegram".
- **Messages appear where you can't see them.** On Account, Body and Tests, the result of a
  button shows at the top of the page while the button is far below.
- **Dead ends.**
  - After saving a session, "Done" lands on "Nothing left to train today": no summary, no
    next session, no link to progress.
  - Errors say "reload the page" with no Retry button.
  - Signed-out states show a bare text link.
- **Cardio uses the strength flow.** A 45-minute zone 2 run is "Set 1 of 1" in steps of 5
  minutes (62 can't be entered), with no clock, a "Start session" button for something you
  log afterwards, and 4 taps. HIIT rounds are labelled "Reps".
- **Bot and web feel like two apps.**
  - Rest today, Swap, Push, habits, settings, the week and the weekly review exist only in
    Telegram.
  - The morning message doesn't link to the web app.
  - Readiness is reachable only from a notice.
- **Re-confirming who you are.** Signing out, signing in and re-typing for a sensitive change
  (fixed by [ADR-0049](../adr/0049-confirm-with-fingerprint.md), #194: a fingerprint prompt in place).

## Part 1: being built now (asked for)

1. **One look for actions and fields.**
   - Base styles for `button`, `input`, `select` and `textarea`: border, 44px minimum height,
     visible focus.
   - Shared primary, secondary and danger button classes, plus a card class, in one file
     instead of copies in 7 files.
   - Headings moved into the base layer so the small titles shrink back.
   - Every action becomes a real button.
2. **Fits a phone.** On narrow screens the nav becomes a bottom tab bar:
   - Today, Progress, Tests, Body, and More (Plan, Readiness, Account, Sign out);
   - 48px tap targets.
   `/plan` gets the same frame, and its Telegram-era copy goes. Photo captions and sparkline
   rows get room to fit.
3. **Messages next to their button**, on Account, Body and Tests.
4. **Retry buttons and a real "Sign in" button** on every error and signed-out state.
5. **Sign-in comes back to where you were** (`/signin?next=/account`).

## Part 2: decide together

### A. Cardio: "Start session" or "Log activity"?

You train cardio first and log it afterwards, so "Start session" with sets is the wrong
model. Options, not exclusive:

| Option | What | Pros | Cons |
| --- | --- | --- | --- |
| A1 **Log activity** (recommended) | One screen: exact minutes (type it, or ±1/±5), activity chips (walk, jog, bike, hike), one Save | Matches what happens; exact numbers; 2 taps | Activity and heart rate need new fields (minutes alone needs none) |
| A2 **Done as planned** | One tap: "Done: 45 min" | Fastest on a normal day | Wrong if you did more or less, so it needs A1 beside it |
| A3 **Timer** | A running clock; for HIIT a 20 s / 10 s interval timer that counts rounds | Useful for HIIT indoors | Pointless for an outdoor walk: the band times it |
| A4 **Import from the band** (Health Connect, already proposed) | The minutes arrive by themselves; you confirm | No typing; real heart-rate zones | Bigger job; needs the bridge app |

**Recommendation:** A1 + A2 for zone 2 and moderate cardio, an A3 interval timer for HIIT
only, and A4 later as the default with A1 as the fallback. After saving a cardio day, show
"This week: 95 of 180-200 zone-2 min".

### B. What should the first screen be?

| Option | What |
| --- | --- |
| B1 **Today as home** (recommended) | One screen answering "what now?": today's session with Start or Log, plus Rest today and Swap; when done, a short summary and what's next; zone 2 minutes this week; anything ready to move up; tests or readiness due; a session left unsaved. Every empty state links to its next step |
| B2 Keep `/session` as is | Fix the dead end only: Done shows the summary and next up |

### C. One app across Telegram and the web

| Idea | Effort |
| --- | --- |
| C1 "Open in app" button on the morning message and on `/today` | S |
| C2 Rest today, Swap and Push on the web (the queue logic already exists) | M |
| C3 Undo on the web (the `/undo` logic already exists) | S |
| C4 The weekly review on the web, with the AI comment under it | M |
| C5 Habits on the web (tick today's habits on Today) | M |
| C6 Settings on the web (message times, nudges, pause) | M |

Telegram would then be for what it does best: the morning nudge, quick voice and text logs,
and alerts. The web app becomes the place you work in.

### D. Navigation

| Option | What |
| --- | --- |
| D1 **Bottom tabs on phones** (being built, Part 1) | Today, Progress, Tests, Body, More |
| D2 Fewer pages | Fold Readiness into Today (as a due card) and Plan into Progress |
| D3 Install as an app (PWA) | A home-screen icon and full screen; no store, no cost |

## Suggested order

1. Part 1 (tonight).
2. A1 + A2 cardio logging, and B1 Today as home: the biggest daily gain.
3. C1 + C2 + C3: one app, not two.
4. C4 weekly review on the web, D3 install as an app.
5. A3 HIIT timer, C5 habits, C6 settings, then A4 import from the band.

## Questions for you

1. Cardio: A1 + A2 as recommended? Should a log carry the activity (walk, jog, bike) and
   average heart rate, or minutes only for now?
2. First screen: B1 Today as home?
3. Should Rest today and Swap live on the web too (C2), or stay in Telegram?
4. Fold Readiness into Today and Plan into Progress (D2)?
5. Install as an app (D3) now, or later?
