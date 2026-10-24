# Our own Android reader for band data: plan

Status: a plan, nothing built (2026-10-24). It would replace HC Webhook as the bridge chosen in
ADR-0055 (Q9), which named "our own Android app writing to the same endpoint" as the later
option. The direction is `platform-and-health-data-proposal.md`, section 4, "What we learned".

## Goal

Band data reaches the coach every day without fiddling on the phone. A small app of our own
reads Health Connect and posts to the ingest the Pi already has, with the same secret and the
same JSON, so nothing on the Pi changes.

## What we know (24 Oct 2026)

- **Mi Fitness writes to Health Connect,** checked on the phone on 24 Oct: heart rate and
  exercise (Mi Fitness is the only app allowed to write them), and the 23 Oct run is there.
  Sleep isn't checked yet.
- **It writes only when it syncs with the band.** Heart rate stopped at 17:29 on 23 Oct and
  caught up to the minute when Mi Fitness was opened the next day. MIUI stops it in the
  background unless its battery saver is off and Autostart is on (`band-import.md` step 3.4).
  Any bridge, ours included, can only send what Mi Fitness has written.
- **HC Webhook has delivered nothing since 19 Oct.** Version 1.9.22 fails on the phone with
  Health Connect's "Rate limited request quota has been exceeded", even for steps alone. It
  reads 48 hours of raw records on every sync, and its dashboard reads every type it may read
  each time it opens, so the quota never refills.
- So there are two problems: Mi Fitness in the background (phone settings) and the bridge
  (this plan).

## What the reader does

### Reads less

Google's advice is to sync from Health Connect's changes rather than raw reads, and to keep
background reads to a minimum, since the background quota is smaller ([rate limiting]). Google
publishes no numbers for either.

- **Changes, not history.** One changes token per type (as [best practices] advise), stored on
  the phone. Each sync asks only for what was written or deleted since the last one. The first
  sync, or one after a token expires, reads the last 48 hours once.
- **Steps:** one aggregate call for today and yesterday, grouped by local day, sent as one
  record per day. The ingest keeps the larger of what a day has and what came (ADR-0055), so a
  daily total sent again is harmless.
- **Heart rate:** the changed heart-rate records, bucketed on the phone into the 1-minute
  `avg`/`min`/`max` buckets HC Webhook sends, so the payload stays small.
- **Sleep and exercise:** the changed records with their Health Connect ids; deletions go in
  `deleted` as `{type, id}`.
- **Resting heart rate** if Health Connect has any; otherwise the coach derives it, as now.
- **Weight isn't read:** Mi Fitness doesn't write it (`band-import.md` step 2).

### Sends the same JSON

- `POST /api/ingest/health-connect` with `Authorization: Bearer <secret>`, the body HC Webhook
  1.9.23 and later send (`timestamp`, `app_version`, an array per type, record ids,
  `deleted`). The coach already reads it; `tests/hcw_payloads.py` describes it.
- `app_version` is `tc-reader/<version>`, so Account > Band import shows which app sent the
  last sync.
- A sync over about 4 MB is split into several posts (the ingest refuses 5 MB). A token moves
  on only after the coach answers 2xx, so a failed send goes again next time.
- HTTPS only, to the one address the person types; no cleartext, no analytics, no other
  network calls.

### Syncs when it can

- **When opened:** the foreground quota is the larger one.
- **In the background, once or twice a day** with WorkManager, if the installed Health Connect
  supports reading in the background (`FEATURE_READ_HEALTH_DATA_IN_BACKGROUND`, which depends on
  the Health Connect version, not Android's [read data]). Without it the reader syncs only when
  opened, and the coach's existing Telegram message ("No band data has arrived for a day") is
  the nudge.

### One screen

- Per type: last read, last sent, records in the last sync.
- **Sync now**.
- **In Health Connect, last 7 days:** how many records of each type each app wrote, so "is Mi
  Fitness writing it?" is one tap.
- The address and the secret, entered once; the secret is encrypted with a key held in the
  Android Keystore and never shown again.
- The last error as it happened: the quota, 401, 413, no network.

### Permissions

Reads Steps, Heart rate, Sleep, Exercise and Resting heart rate, plus reading in the
background. Nothing else, and no write permissions.

## Build and ship

- **Where:** `android/` in this repo, with its own `android/CLAUDE.md`, the same PR flow and
  review. Kotlin, Jetpack Compose, `androidx.health.connect:connect-client`, WorkManager; the
  fewest dependencies that do the job, each with a reason in its PR.
- **No tools needed on the desktop:** a CI job, run only when `android/` changes, builds the
  app, runs its unit tests and Android lint, and checks the Gradle wrapper.
- **One contract, tested on both sides:** the app's tests build a sync from fixed records and
  compare it with a sample committed in the repo; a backend test posts that same sample to the
  ingest and checks what is taken.
- **Releases:** a release-please component of its own (`android-v0.1.0` and so on), so a
  backend release doesn't offer a phone update. The signed APK is attached to its GitHub
  release; Obtainium, already on the phone, installs and updates it from there.
- **Signing key:** made once, kept as GitHub Actions secrets and backed up encrypted in
  `~/.secrets`. Android refuses an update signed with another key, so losing it means
  uninstalling and setting up again. Making and uploading it needs an OK first.
- **Cost:** none. Google Play, for a public app later, adds a one-off developer fee, a
  health-data declaration and Google's review.

## Order

Each PR under about 400 lines, not counting the Gradle wrapper and generated files.

1. ADR (bridge: our reader), `android/` skeleton: the screen with the address and secret, the
   CI job.
2. Reading and sending: changes tokens, the steps aggregate, heart-rate buckets, the payload
   and its contract test on both sides.
3. The background sync and the "In Health Connect, last 7 days" view.
4. Signing, the release component, and `band-import.md` rewritten for the reader, keeping HC
   Webhook as a fallback until the reader has a week of good syncs.

About three to four days of work.

## Risks

- **The quota still exists.** We use far less of it, but Google doesn't publish the limits.
  The screen shows the quota error when it happens.
- **MIUI can stop the reader too,** as it stops Mi Fitness: the same battery settings.
- **A new stack to maintain:** Kotlin and Gradle beside Python and TypeScript, and a Health
  Connect library that still changes between versions.
- **Android only,** which fits the plan (Android first).

## Options considered

| Option | Why not, for now |
| --- | --- |
| Keep HC Webhook and tune it | Tried since 19 Oct (runbook "Unsticking HC Webhook"); fails even for steps alone |
| Change HC Webhook upstream to use changes | AGPL, someone else's app and pace; ours would still depend on it |
| Gadgetbridge reading the band directly | Writes to Health Connect, but Band 9 support isn't confirmed ([Gadgetbridge Xiaomi]) and it would replace Mi Fitness |
| Google Health API (cloud) | Doesn't cover Mi Fitness (ADR-0055) |

## Questions for Liam

Answered with these defaults unless Liam says otherwise:

1. **Same repo** (`android/`), not a separate one.
2. **Foreground only is acceptable** if the phone's Health Connect can't read in the
   background, with the existing Telegram gap message as the nudge.
3. **Sleep:** does Health Connect > Data and access > Sleep list Mi Fitness entries? If not,
   sleep needs fixing in Mi Fitness before any bridge can send it.

[rate limiting]: https://developer.android.com/health-and-fitness/health-connect/rate-limiting
[best practices]: https://d.android.com/guide/health-and-fitness/health-connect/best-practices
[read data]: https://developer.android.com/health-and-fitness/health-connect/read-data
[Gadgetbridge Xiaomi]: https://gadgetbridge.org/gadgets/wearables/xiaomi/
