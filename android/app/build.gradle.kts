plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

// android/VERSION is the one version: 1.2.3 is versionCode 10203. A release is made when it moves.
val appVersion = rootProject.file("VERSION").readText().trim()
val (major, minor, patch) = appVersion.split(".").map { it.toInt() }

android {
    namespace = "com.vybedev.coach.reader"
    // The API the code compiles against (androidx.core 1.19 needs 37). What the phone does is
    // decided by minSdk and targetSdk, which stay explicit: AGP 9 would default targetSdk to
    // compileSdk.
    compileSdk = 37

    defaultConfig {
        applicationId = "com.vybedev.coach.reader"
        minSdk = 28
        targetSdk = 36
        versionCode = major * 10_000 + minor * 100 + patch
        versionName = appVersion
        // The one place the secret may go (security review of 24 Oct): not typed, so a pasted
        // look-alike or a moment with the unlocked phone can't send it elsewhere.
        buildConfigField("String", "COACH_URL", "\"https://coach.vybe-dev.com/api/ingest/health-connect\"")
    }

    buildTypes {
        release {
            // Built unsigned: the release workflow signs it with apksigner, so the key never
            // meets Gradle or its plugins (ADR-0070, security review of 24 Oct).
            isMinifyEnabled = false
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        warningsAsErrors = false
        abortOnError = true
        // Versions move on purpose, in their own PRs.
        disable += setOf("GradleDependency", "NewerVersionAvailable", "AndroidGradlePluginVersion")
    }
}

dependencies {
    // Health Connect: the data this app exists to read.
    implementation("androidx.health.connect:connect-client:1.1.0")
    // The one screen, and the permission request's result.
    implementation(platform("androidx.compose:compose-bom:2025.10.01"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0")
    // The background sync, once or twice a day: Android's own scheduler, which survives reboots
    // and needs no exact alarm or foreground service (Android 12, MIUI).
    implementation("androidx.work:work-runtime-ktx:2.12.0")
    // JSON built as JsonObject, no compiler plugin; also what the unit tests parse.
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.12.0")

    testImplementation("junit:junit:4.13.2")
}
