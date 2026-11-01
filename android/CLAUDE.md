# android/CLAUDE.md

Rules for `android/`, the band reader (ADR-0070, `docs/specs/android-reader.md`). The root
`CLAUDE.md` still applies.

## Layout

```
VERSION                     the app's one version; a release is made on main when it moves
build.gradle.kts            plugin versions; app/build.gradle.kts has the dependencies
gradle/verification-metadata.xml   their checksums, written in CI (see Building)
app/expected-apk.txt        what the release APK declares (package, SDKs, permissions); CI checks it
app/src/main/java/.../      Payload.kt, Delivery.kt, Reads.kt, Runs.kt and Week.kt (pure:
                            what a sync sends, whether it all arrived, how many reads it may
                            make, what a background run may do and leaves behind, the 7-day
                            view's wording),
                            HealthReader.kt (every Health Connect call),
                            Sync.kt (one sync at a time), Background.kt (WorkManager, where
                            Health Connect allows it), Sender.kt (HTTPS post), Store.kt and
                            SecretBox.kt (state; the secret under a Keystore key)
app/src/test/               JVM unit tests for the pure parts
```

## Building

- There are no Android tools on the desktop: CI (`.github/workflows/android.yml`) runs
  `gradle -p android :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
  :app:assembleRelease` with Gradle 9.7.1 and JDK 17. There's no Gradle wrapper; the workflow
  pins the version.
- Kotlin is AGP's built-in Kotlin (no `org.jetbrains.kotlin.android` plugin). Its version is the
  `kotlin-gradle-plugin` classpath line in `build.gradle.kts` and must match the Compose compiler
  plugin's. `minSdk` and `targetSdk` stay explicit: AGP 9 defaults an unset targetSdk to compileSdk.
- Dependency verification: `gradle/verification-metadata.xml` holds a sha256 for every plugin
  and library the build resolves, and the build fails on any artifact without a matching one.
  Never write or edit a checksum by hand. When dependencies or plugins change (Dependabot's
  Gradle PRs too, whose `android.yml` check fails until this is done), on that PR's branch:
  1. Run `gh workflow run gradle-verification.yml --ref <branch>` twice; it rebuilds the file
     from scratch with the same tasks as `android.yml` and keeps it as an artifact.
  2. `gh run download <id> -n verification-metadata -D <dir outside the repo>` for both runs;
     the two files must be identical.
  3. Diff one against the committed file: only the components that changed version may
     differ. A new checksum for a version already listed means stop and find out why.
  4. Commit it to the branch as `android/gradle/verification-metadata.xml`.
  The checksums are Linux-only for native tools such as aapt2, as CI is the only place that builds.
- What the APK declares: after the build, `android.yml` reads the unsigned release APK with
  `aapt2` and compares package, minSdk, targetSdk and every permission (merged ones included)
  with `app/expected-apk.txt`, and versionCode with `VERSION`, on pull requests too. A toolchain
  or library update that changes any of them fails there; change the file only on purpose, with
  the reason in the PR.
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
  first sync's 24 hours (`FIRST_SYNC_HOURS`), no reads on screen open beyond the permission check.
- **The coach's JSON is the contract** (ADR-0055, `backend/tests/hcw_payloads.py`). Change the
  body only together with the backend test that posts it (`_reader_sync` in
  `backend/tests/api/test_ingest.py`).
- **Nothing moves on until the coach answered 2xx:** tokens and "sent" totals are saved after
  the last post succeeded (`Delivery.kt`). The one exception: a batch refused for good (413 or
  422) three syncs in a row is skipped, and the screen says how many posts were lost.
- Keep `Payload.kt`, `Delivery.kt`, `Reads.kt`, `Runs.kt` and `Week.kt` free of Android imports so they stay
  unit-tested on the JVM.
- New dependencies need a reason in the PR description, as everywhere in the repo.
