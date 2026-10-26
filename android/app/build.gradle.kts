plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// android/VERSION is the one version: 1.2.3 is versionCode 10203. A release is made when it moves.
val appVersion = rootProject.file("VERSION").readText().trim()
val (major, minor, patch) = appVersion.split(".").map { it.toInt() }

android {
    namespace = "com.vybedev.coach.reader"
    compileSdk = 36

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

kotlin {
    jvmToolchain(17)
}

dependencies {
    // Health Connect: the data this app exists to read.
    implementation("androidx.health.connect:connect-client:1.1.0")
    // The one screen, and the permission request's result.
    implementation(platform("androidx.compose:compose-bom:2025.10.01"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.4")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    // The background sync, once or twice a day: Android's own scheduler, which survives reboots
    // and needs no exact alarm or foreground service (Android 12, MIUI).
    implementation("androidx.work:work-runtime-ktx:2.11.2")
    // JSON built as JsonObject, no compiler plugin; also what the unit tests parse.
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")

    testImplementation("junit:junit:4.13.2")
}
