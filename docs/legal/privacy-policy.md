# Privacy notice (draft)

> Draft, not published and not legal advice. Items in [brackets] are open; see
> [README.md](README.md). Written from how the app works on 2026-10-10.

## Who is responsible

Liam Doyle, [address], liamdoyledev@gmail.com ("we"). Questions about your data and requests to
exercise your rights go to that address.

## What Training Coach stores, and why

Training Coach is a training app: it plans your sessions, keeps what you did and shows your
progress. To do that it stores:

| Data | Why | Legal basis |
| --- | --- | --- |
| Your Telegram user id and settings (reminder times, habits) | To know it's you on Telegram and send reminders when you asked | Contract (Art. 6(1)(b) GDPR) |
| Workouts, sets, test results, habit check-offs, where you are in the plan | The training itself | Contract (Art. 6(1)(b)) |
| Body measurements (bodyweight, waist, chest, upper arm, thigh, resting heart rate) and progress photos | Showing your progress. These are **health data** | Your explicit consent (Art. 9(2)(a)), which you can withdraw at any time [consent step in sign-up] |
| Answers to the readiness questions | Warning you before hard efforts if a doctor should be asked first. **Health data** | Your explicit consent (Art. 9(2)(a)) |
| Passkeys (the public half only), signed-in browsers (a label and when last seen), sign-in links (stored only as a hash) | Signing you in securely, letting you sign out lost devices | Contract (Art. 6(1)(b)); security (Art. 6(1)(f)) |
| A short record of account events (signed in, passkey added, data downloaded or erased) | Security, and showing you what happened | Legitimate interest in keeping your account safe (Art. 6(1)(f)) |
| For 5 minutes, a hash of your IP address when you start a passkey sign-in | Stopping floods of sign-in attempts | Legitimate interest (Art. 6(1)(f)) |

Progress photos are stripped of their metadata (location, camera, time) before they're stored.

Voice notes you send the bot are transcribed and then discarded: they are never written to
disk, and the transcript isn't logged.

There are no adverts, no tracking, no analytics, and nothing is sold or shared for marketing.
The site sets one cookie, which keeps you signed in; it is strictly necessary, so no cookie
banner is needed (§ 25(2) TDDDG).

## Where the data is, and who else handles it

Your data is stored on a server we run ourselves, in [Germany]. These services handle some of it
for us:

| Service | What it sees | Where |
| --- | --- | --- |
| Telegram (the bot) | The messages between you and the bot, as for any Telegram chat | Telegram's servers [entity and location] |
| Groq, Inc. | Voice notes, to turn them into text, and workout logs the app couldn't read itself, to read them. Not stored by us afterwards | USA [transfer safeguard: EU-US Data Privacy Framework or standard contractual clauses; DPA] |
| Cloudflare, Inc. | All traffic to the website passes through Cloudflare (protection against attacks). Encrypted backups are kept in Cloudflare R2 storage; Cloudflare can't read them | USA / [R2 location] (EU-US Data Privacy Framework) [DPA] |
| Healthchecks.io | Only whether the server is up. No personal data | Latvia (EU) |

## How long it's kept

Until you erase it. You can erase everything at once on the Account page ("Erase all my data").
Backups that still contain it are deleted within 5 weeks: nightly backups after at most 5 weeks,
all other copies after 35 days. Signed-in browsers end after 30 days unused and at most 90 days
after sign-in.

## Your rights

You can, at any time:

- see everything stored about you, and take it with you: "Download all my data" on the Account
  page (Art. 15, 20);
- have it corrected (Art. 16) or erased (Art. 17): "Erase all my data", or ask us;
- restrict or object to its use (Art. 18, 21);
- withdraw your consent for health data, without affecting what was done before (Art. 7(3));
  measurements, photos and readiness answers are then erased [today only by erasing
  everything; a per-category erase is needed before launch];
- complain to a data protection authority, for example [the authority for our address].

## Security

Sign-in is by passkey (your fingerprint or face on your own device). Connections are encrypted,
backups are encrypted before they leave the server, and the server only accepts traffic through
Cloudflare. Details are in the project's threat model.

## Changes

If this notice changes in a way that matters, the app tells you before it applies.
