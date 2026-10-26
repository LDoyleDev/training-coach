# ADR-0070: Our own Android reader for band data

- Status: Accepted 2026-10-26 by Liam after reader 0.0.4's first clean sync (3 reads; 2 days of
  steps and 4,967 heart-rate samples in one post); he chose not to wait for the full 3-day trial
- Date: 2026-10-24
- Deciders: Liam

## Context

ADR-0055 chose HC Webhook, an open-source app, as the bridge from Health Connect to the Pi
(Q9), and named "our own Android app writing to the same endpoint" as the later option. Only
steps ever arrived, and nothing since 2026-10-19. HC Webhook 1.9.22 ran out of Health Connect's
read quota on every sync. On 24 Oct the newest version (1.9.31, which syncs from Health
Connect's changes) was tried: a one-day sync of six types failed on sleep with the same
quota error after about nine minutes, and nothing reached the coach. Liam chose to build our
own reader rather than retry. The plan and its review are in `docs/specs/android-reader.md`.

## Decision

- A small Android app of our own, in `android/` in this repo (Kotlin, Jetpack Compose,
  `androidx.health.connect:connect-client`), reads Health Connect and posts to the existing
  `POST /api/ingest/health-connect` with the person's ingest secret and the JSON HC Webhook
  sends (ADR-0055). The Pi's ingest is unchanged.
- It reads as little as it can: steps as a daily aggregate, sent only when a day's total
  changed; everything else from Health Connect's changes, one token per type, moved on only
  after the coach answered 2xx. Heart rate goes as raw samples, and the coach buckets them.
- It syncs when opened (the foreground quota), and later once or twice a day in the
  background if the phone's Health Connect allows it.
- **Signing:** one release key from the first build, kept as secrets of the GitHub environment
  `android-release`, which needs Liam's approval for every run that uses it. On the desktop it
  is in `~/.secrets/training-coach/android`, with a backup there and on the Pi
  (`~/keys-backup/training-coach/android-signing-backup.tar.age`), encrypted with age to the
  Training Coach backup key (`docs/runbooks/backup-restore.md`) and the desktop's Linux key. The key never meets Gradle: CI
  builds an unsigned APK with no secrets, and the release job only signs it with apksigner and
  checks the certificate against the digest pinned in `android/SIGNING_CERT_SHA256` (security
  review of 24 Oct: a compromised build dependency could otherwise take the key). Accepted for
  now: a compromised build dependency could still change the unsigned APK it hands over, and it
  would be signed, since the digest check proves who signed, not what. Gradle dependency
  verification (checksums of every plugin and library, committed) is the follow-up that
  closes it.
- **Builds:** CI builds and tests `android/` when it changes. A release is a GitHub
  pre-release tagged `android-v<version>` with the signed APK, made by its own workflow (not
  release-please), and installed with Obtainium.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Our own reader (chosen) | Reads only what changed; we control quota use, scheduling and what is sent | A new stack (Kotlin, Gradle) to maintain; no local Android build, so CI round trips |
| Keep HC Webhook, one more fair retry | No code | Two versions failed on the same quota; it reads types we don't need |
| Fork HC Webhook | Its permission and scheduling code exists | Someone else's large codebase to merge from |
| Gadgetbridge in place of Mi Fitness | Would also fix Mi Fitness writing only when opened | Band 9 support unconfirmed; re-pairing; loses Mi Fitness |
| Health Connect's own export | No app code | Not confirmed on Android 12's Health Connect; a day late; undocumented format |

## Consequences

- **Trial:** the first build read steps and heart rate only, in the foreground, with HC
  Webhook switched off, and was to sync for three days before this ADR was accepted. Reader
  0.0.3 hit the quota after 202 reads, all its own fault (an empty page token read as one more
  page, 26 Oct); 0.0.4 ends a read on an empty token and makes at most 20 reads a sync, and its
  first sync took 3. Liam accepted the ADR after that sync rather than wait the three days
  (Status). A quota error with a minimal read pattern would still rule out readers built on
  Health Connect reads, and Gadgetbridge or the export would come next.
- Mi Fitness writes to Health Connect only when it syncs with the band, which on this phone
  means when it is opened (`docs/runbooks/band-import.md` step 5.3). No bridge fixes that.
- The repo's root release-please package ignores `android/`, so an app change doesn't bump the
  coach's version; the Pi's auto-deploy only takes `v*` tags, so `android-v*` tags never deploy.
- The threat model gets a row for the reader: the ingest secret on the phone, encrypted with an
  Android Keystore key and never shown again; HTTPS only to the coach's address built into the app (not typed, 24 Oct review); no backup of
  app data (`allowBackup=false`); no third-party SDKs or analytics; and the signing key,
  whose leak would let someone ship an update, behind the protected environment.
- Account's band-import text shows the sending app's own version string, not "HC Webhook".
