# ADR-0070: Our own Android reader for band data

- Status: Proposed (accepted once the first build passes the trial in Consequences)
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
  `android-release`, which needs Liam's approval for every run that uses it, and backed up
  encrypted with age in `~/.secrets/training-coach/android`.
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

- **Trial before Accepted:** the first build reads steps and heart rate only, in the
  foreground, with HC Webhook switched off (not running beside it). If it syncs for three days
  after opening Mi Fitness without a quota error and the data shows on Account > Band import,
  this ADR is accepted. A quota error with this minimal pattern rules out readers built on
  Health Connect reads, and Gadgetbridge or the export come next.
- Mi Fitness writes to Health Connect only when it syncs with the band, which on this phone
  means when it is opened (`docs/runbooks/band-import.md` step 6.3). No bridge fixes that.
- The repo's root release-please package ignores `android/`, so an app change doesn't bump the
  coach's version; the Pi's auto-deploy only takes `v*` tags, so `android-v*` tags never deploy.
- The threat model gets a row for the reader: the ingest secret on the phone, encrypted with an
  Android Keystore key and never shown again; HTTPS only to the one address typed; no backup of
  app data (`allowBackup=false`); no third-party SDKs or analytics; and the signing key,
  whose leak would let someone ship an update, behind the protected environment.
- Account's band-import text shows the sending app's own version string, not "HC Webhook".
