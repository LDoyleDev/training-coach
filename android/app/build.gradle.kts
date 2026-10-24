plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// android/VERSION is the one version: 1.2.3 is versionCode 10203. A release is made when it moves.
val appVersion = rootProject.file("VERSION").readText().trim()
val (major, minor, patch) = appVersion.split(".").map { it.toInt() }

// Only the release workflow has the key (GitHub environment android-release, ADR-0070).
val keystorePath: String? = System.getenv("ANDROID_KEYSTORE_PATH")
val keystorePassword: String? = System.getenv("ANDROID_KEYSTORE_PASSWORD")

android {
    namespace = "com.vybedev.coach.reader"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.vybedev.coach.reader"
        minSdk = 28
        targetSdk = 36
        versionCode = major * 10_000 + minor * 100 + patch
        versionName = appVersion
    }

    signingConfigs {
        if (keystorePath != null && keystorePassword != null) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = keystorePassword
                storeType = "pkcs12"
                keyAlias = "tc-reader"
                keyPassword = keystorePassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
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
    // JSON built as JsonObject, no compiler plugin; also what the unit tests parse.
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")

    testImplementation("junit:junit:4.13.2")
}
