// Versions in one place; CI runs Gradle 9.7.1 (.github/workflows/android.yml), no wrapper.
buildscript {
    dependencies {
        // AGP 9 compiles Kotlin itself (built-in Kotlin) and brings Kotlin Gradle plugin 2.2.10;
        // this line picks the Kotlin version, which must match the Compose compiler plugin below.
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.4.21")
    }
}

plugins {
    id("com.android.application") version "9.3.3" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.4.21" apply false
}
