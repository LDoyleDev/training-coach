# android/CLAUDE.md

Rules for `android/`, the band reader (ADR-0070, `docs/specs/android-reader.md`). The root
`CLAUDE.md` still applies.

## Layout

```
VERSION                     the app's one version; a release is made on main when it moves
build.gradle.kts            plugin versions; app/build.gradle.kts has the dependencies
app/src/main/java/.../      Payload.kt (pure: what a sync sends), HealthReader.kt (every Health
                            Connect call), Sync.kt (one sync at a time), Sender.kt (HTTPS post),
                            Store.kt + SecretBox.kt (state; the secret under a Keystore key)
app/src/test/               JVM unit tests for the pure parts
```

## Building

- There are no Android tools on the desktop: CI (`.github/workflows/android.yml`) runs
  `gradle -p android :app:testDebugUnitTest :app:lintDebug :app:assembleDebug` with Gradle
  8.14.4 and JDK 17. There's no Gradle wrapper; the workflow pins the version.
- A release: bump `VERSION` in a PR. After merge, the workflow waits for Liam's approval of
  the `android-release` environment, signs the APK and publishes the pre-release
  `android-v<version>`. Never put the key or its password anywhere else.
- `adb` is on the desktop for the phone's logs: `adb logcat --pid=$(adb shell pidof
  com.vybedev.coach.reader)`.

## Rules

- **Read as little as possible** (the whole point, ADR-0070): no raw history reads beyond the
  first sync's 48 hours, no reads on screen open beyond the permission check.
- **The coach's JSON is the contract** (ADR-0055, `backend/tests/hcw_payloads.py`). Change the
  body only together with a backend test that posts it.
- **Nothing moves on until the coach answered 2xx:** tokens and "sent" totals are saved after
  the last post succeeded.
- Keep `Payload.kt` free of Android imports so it stays unit-tested on the JVM.
- New dependencies need a reason in the PR description, as everywhere in the repo.
