# Our own Android reader for band data: plan

Status: being built (2026-10-24), decision in ADR-0070 (Accepted 26 Oct after reader 0.0.4's
first clean sync; Liam chose not to wait for the 3-day trial). HC Webhook 1.9.31 still ran out of Health Connect's quota on the phone on 24 Oct
(`band-import.md`), so Liam chose to build the reader. This plan replaces HC Webhook as the
bridge chosen in ADR-0055 (Q9). The review of 24 Oct is folded in below, and its full list is
in `docs/sessions/2026-10-24-evals-dst.md`.

## Goal

Band data reaches the coach every day with as little fiddling on the phone as possible. A small
app of our own reads Health Connect and posts to the ingest the Pi already has, with the same
secret and the same JSON, so the ingest doesn't change.

## What we know (24 Oct 2026)

- **Mi Fitness writes to Health Connect,** checked on the phone on 24 Oct: heart rate and
  exercise (Mi Fitness is the only app allowed to write them), and the 23 Oct run is there.
  Sleep isn't checked yet.
- **It writes only when it syncs with the band.** Heart rate stopped at 17:29 on 23 Oct and
  caught up to the minute when Mi Fitness was opened the next day, although its battery saver
  was already off and Autostart on (`band-import.md` step 3.4). Any bridge, ours included, can
  only send what Mi Fitness has written, so Mi Fitness needs opening (by hand or automation).
- **HC Webhook has delivered nothing since 19 Oct.** Version 1.9.22 ran out of Health
  Connect's quota on every sync. Version 1.9.31 (24 Oct): a one-day sync of six types failed on
  sleep with the same quota error after about nine minutes, and nothing reached the coach.
- So there are two problems: Mi Fitness waits to be opened, and the bridge runs out of quota.
  This plan is for the second.

## What the reader does

### Reads less

Google's advice is to sync from Health Connect's changes rather than raw reads, and to keep
background reads to a minimum, since the background quota is smaller ([rate limiting]). Google
publishes no numbers for either.

- **Changes, not history.** One changes token per type (as [best practices] advise), stored on
  the phone. Each sync asks only for what was written or deleted since the last one. The first
  sync, or one after a token expires, reads the last 24 hours once (`FIRST_SYNC_HOURS`; it was
  48 until the trial's first sync hit the quota on 24 Oct), in pages of 5,000, the most Health
  Connect allows; a gap longer than that doesn't come across. A quota error names the read that
  hit it and how many reads the sync had made.
- **At most 20 reads a sync** (`Reads.kt`). On 26 Oct reader 0.0.3 hit the quota after 202 reads:
  Health Connect on Android 12 ends a history read with an empty page token, not null, and the
  reader read the same day again and again. An empty token now ends the read. At the limit, a
  history read sends what it read and keeps its token (failing would leave no token, so every
  later sync would spend the same reads again), and a long run of changes stops where it got to
  and goes on at the next sync. The result line shows each sync's read count. A normal sync
  makes four: the steps aggregate, then one changes read each for sleep, exercise and heart
  rate (heart rate last, as the heaviest, so its catch-up can't leave sleep unread). A type's
  first sync takes two (a token and a page of history), so the first sync after updating from
  0.0.4 takes six, and a first sync on a new phone seven or more.
- **Changes are collapsed per record id, last one wins,** so a record written and deleted in
  the same batch isn't sent as both (the ingest applies deletions first).
- **Steps:** one aggregate call for today and yesterday, grouped by local day, and a day is sent
  only when its total changed since the last send. Sending unchanged totals every time would
  keep the coach's "nothing new from the band" alert from ever firing (ADR-0055).
- **Heart rate:** the changed heart-rate records' raw samples as `{bpm, time}`. The ingest
  already averages samples per minute.
- **Sleep and exercise:** the changed sessions with their Health Connect ids, each type with
  its own changes token (a deletion names only the record's id, so its token says its type);
  deletions go in `deleted` as `{type, id}`, `sleep` or `exercise`. Sleep goes with its stages,
  exercise with its type, as HC Webhook sends them. Heart-rate deletions are dropped: the coach
  keeps heart rate per minute and can't apply them.
- **Resting heart rate** isn't read: the coach derives it from heart rate.
- **Weight isn't read:** Mi Fitness doesn't write it (`band-import.md` step 2).

### Sends the same JSON

- `POST /api/ingest/health-connect` with `Authorization: Bearer <secret>`, the body HC Webhook
  1.9.23 and later send (`timestamp`, `app_version`, an array per type, record ids,
  `deleted`). The coach already reads it; `tests/hcw_payloads.py` describes it.
- What the ingest needs from each record, or it skips or duplicates it: `bpm` on a heart-rate
  sample, `metadata.data_origin` (the writing app, e.g. `com.mi.health`), `deleted[].type` of
  `sleep` or `exercise`, and times with their full precision.
- `app_version` is `tc-reader/<version>`, shown on Account > Band import.
- A sync over about 4 MB is split into several posts (the ingest refuses 5 MB). A token moves
  on only after the post holding its changes gets a 2xx, so a failed send goes again next time.
- **A post refused for good** (413 or 422) three times in a row is skipped, the token moves on,
  and the screen says what was dropped, so one bad batch can't block every later sync.
- Only one sync runs at a time ("Sync now" and the background job share one lock), so a stale
  token never overwrites a newer one.
- HTTPS only, to the coach's ingest address built into the app (`BuildConfig.COACH_URL`,
  checked for host, path, no user part and no port) and never typed, so a look-alike can't get
  the secret; redirects aren't followed; no cleartext, no analytics, no other
  network calls.

### Syncs when it can

- **When opened, or on "Sync now":** the foreground quota is the larger one.
- **In the background, about every 12 hours** with WorkManager (0.0.6, `Background.kt`), if
  the installed Health Connect supports reading in the background
  (`FEATURE_READ_HEALTH_DATA_IN_BACKGROUND`, checked with its feature client: it depends on the
  Health Connect version, not Android's [read data]). Only then does the screen ask for the
  background-read permission, and the job is scheduled only once it, every read permission and
  the secret are there. A periodic job with a network constraint: no exact alarm and no
  foreground service, which Android 12 and MIUI restrict, so Android picks the time and a sync
  can come hours late. It shares Sync now's lock and its read limit, and a failed one isn't
  retried at once (that would spend more quota): the next run sends it again. One that sent
  nothing (the quota, no network) is shown on the screen the next time it is opened. Without
  the feature nothing is scheduled, the screen says the reader syncs only when opened, and
  the coach's existing Telegram message ("No band data has arrived for a day") is the nudge.

### One screen

- The secret, entered once in a password field (screenshots of the screen are blocked). The secret is encrypted with a key held in the
  Android Keystore and never shown again.
- **Sync now**, and **Test**, which posts `{"test": true}` to check the secret.
- Per type: last read, last sent, records in the last sync.
- The last error as it happened: the quota, 401, 413, no network.
- **In Health Connect, last 7 days** (0.0.6): per type, how much there is (steps, heart-rate
  samples, hours of sleep and exercise) and which apps wrote it, from one aggregate a type and
  its data origins: four reads, only when tapped. Reading 7 days of raw records would spend the
  quota this plan is saving. Apps go by the names the person knows; the origin "_platform",
  which is no app but Health Connect's own name for data no installed app wrote, reads
  "Health Connect itself" (0.0.7).

### Permissions and Android 12

- Reads Steps, Heart rate, Sleep and Exercise, plus reading in the background where Health
  Connect supports it. Nothing else, and no write permissions.
- On Android 13 and lower, Health Connect's permission screen only opens for an app that
  declares the permissions-rationale activity and a `<queries>` entry for Health Connect.
- `allowBackup=false`, so the secret and tokens never go to a cloud backup.
- Android 12's "Pause app activity if unused" can cancel background jobs of an app that is
  rarely opened: the runbook says to turn it off.

## Build and ship

- **Where:** `android/` in this repo, with its own `android/CLAUDE.md`, the same PR flow and
  review. Kotlin, Jetpack Compose, `androidx.health.connect:connect-client`, WorkManager;
  the fewest dependencies that do the job, each with a reason in its PR.
- **No Android tools needed on the desktop to build:** a CI workflow builds the app, runs its
  unit tests and Android lint whenever `android/` changes. It isn't a required check, so PRs
  that don't touch `android/` never wait for it. `adb` is installed on the desktop for reading
  the phone's logs during the trial.
- **One contract, tested on both sides:** the app's tests (`PayloadTest.kt`) build a sync from
  fixed records and check its JSON; a backend test (`_reader_sync` in `test_ingest.py`) posts
  the same records, as that JSON, to the ingest and checks what is taken and deleted.
- **Signing from the first build:** one release key, kept as secrets of the GitHub environment
  `android-release`, which needs Liam's approval for every run that uses it; where it is kept
  and backed up: ADR-0070, Decision. A debug key changes per CI runner,
  so every build would mean uninstalling and setting up again.
- **Releases:** when `android/` changes on main and its version moved, a workflow of its own
  builds the signed APK in that environment and publishes a GitHub pre-release tagged
  `android-v<version>`. Obtainium, filtered to `android-v` tags, installs and updates it. The
  root release-please package ignores `android/`, so app changes don't bump the coach's
  version, and the Pi only deploys `v*` tags.
- **Cost:** none. Google Play, for a public app later, adds a one-off developer fee, a
  health-data declaration and Google's review.

## Order

Each PR under about 400 changed lines, not counting generated files.

1. **Spike:** ADR-0070 and this update first, then the app with the secret, Test,
   Sync now reading steps and heart rate only, the last error; the CI workflow, signing and
   the pre-release workflow. Trial: HC Webhook switched off, opening Mi Fitness and then the
   reader. Done: 0.0.4's first sync took 3 reads (0.0.3's took 202, see "At most 20 reads"),
   and Liam accepted ADR-0070 after it without waiting the planned three days.
2. Sleep, exercise and deletions, with the contract test on both sides. Done in reader 0.0.5
   (26 Oct); the screen asks once to allow reading sleep and exercise.
3. The background sync and the "In Health Connect, last 7 days" view. Done in reader 0.0.6
   (26 Oct).
4. `band-import.md` rewritten for the reader; Account and the bot name the sending app from its
   version string instead of "HC Webhook"; HC Webhook retired. Done (26 Oct): with no version
   yet, the reader is assumed.

## Risks

- **An expired changes token loses deletions.** Health Connect keeps a token for about 30 days;
  after that the reader reads the last 24 hours again, which brings back what was written but
  not what was deleted meanwhile. A night or workout deleted in Health Connect during that gap
  stays in the coach until it is deleted there by hand (review of #374).
- **The quota still exists.** We use far less of it, but Google doesn't publish the limits.
  The screen shows the quota error when it happens, with the read that hit it and the sync's
  read count, so a reader bug that loops (0.0.3's 202 reads) is told apart from the limit. A
  quota error with a minimal read pattern would rule out readers built on Health Connect reads
  (ADR-0070).
- **Mi Fitness still waits to be opened,** so a daily open (or automation) stays part of the
  routine whatever the bridge.
- **MIUI can stop the reader too,** as it stops Mi Fitness: the same battery settings.
- **A new stack to maintain:** Kotlin and Gradle beside Python and TypeScript, and a Health
  Connect library that still changes between versions.
- **Android only,** which fits the plan (Android first).

## Options considered

ADR-0070 lists the options and why each lost: one more HC Webhook retry, a fork of it,
Gadgetbridge in place of Mi Fitness, and Health Connect's own export.

[rate limiting]: https://developer.android.com/health-and-fitness/health-connect/rate-limiting
[best practices]: https://d.android.com/guide/health-and-fitness/health-connect/best-practices
[read data]: https://developer.android.com/health-and-fitness/health-connect/read-data
