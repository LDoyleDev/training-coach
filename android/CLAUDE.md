# android/CLAUDE.md

Rules for `android/`, the band reader (ADR-0070, `docs/specs/android-reader.md`). The root
`CLAUDE.md` still applies.

## Layout

```
VERSION                     the app's one version; a release is made on main when it moves
build.gradle.kts            plugin versions; app/build.gradle.kts has the dependencies
app/src/main/java/.../      Payload.kt and Delivery.kt (pure: what a sync sends, and whether
                            it all arrived), HealthReader.kt (every Health Connect call),
                            Sync.kt (one sync at a time), Sender.kt (HTTPS post), Store.kt and
                            SecretBox.kt (state; the secret under a Keystore key)
app/src/test/               JVM unit tests for the pure parts
```

## Building

- There are no Android tools on the desktop: CI (`.github/workflows/android.yml`) runs
  `gradle -p android :app:testDebugUnitTest :app:lintDebug :app:assembleDebug` with Gradle
  8.14.4 and JDK 17. There's no Gradle wrapper; the workflow pins the version.
- A release: bump `VERSION` in a PR. After merge, the build job makes an unsigned APK (no
  secrets), then the workflow waits for Liam's approval of the `android-release` environment,
  signs it with apksigner only (no Gradle there), checks its signer against
  `SIGNING_CERT_SHA256` (the public certificate's digest, not a secret) and publishes the
  pre-release `android-v<version>`. Never put the key or its password anywhere else, and never
  give Gradle the key.
- `adb` is on the desktop for the phone's logs: `adb logcat --pid=$(adb shell pidof
  com.vybedev.coach.reader)`.

## Rules

- **Read as little as possible** (the whole point, ADR-0070): no raw history reads beyond the
  first sync's 48 hours, no reads on screen open beyond the permission check.
- **The coach's JSON is the contract** (ADR-0055, `backend/tests/hcw_payloads.py`). Change the
  body only together with the backend test that posts it (`_reader_sync` in
  `backend/tests/api/test_ingest.py`).
- **Nothing moves on until the coach answered 2xx:** tokens and "sent" totals are saved after
  the last post succeeded (`Delivery.kt`). The one exception: a batch refused for good (413 or
  422) three syncs in a row is skipped, and the screen says how many posts were lost.
- Keep `Payload.kt` and `Delivery.kt` free of Android imports so they stay unit-tested on the JVM.
- New dependencies need a reason in the PR description, as everywhere in the repo.
