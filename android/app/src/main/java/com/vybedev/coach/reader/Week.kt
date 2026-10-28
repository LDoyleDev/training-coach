package com.vybedev.coach.reader

import java.time.Duration

/**
 * The "In Health Connect, last 7 days" view: per type, how much Health Connect has and which
 * apps wrote it, from one aggregate a type (ADR-0070: a week of raw records would spend the
 * quota). Pure, so the wording is unit-tested on the JVM.
 */

/** One type's week: [amount] null when Health Connect has none of it. */
data class WeekType(val type: String, val amount: String?, val apps: Set<String>)

/**
 * Apps the phone has, by the name the person knows; others go by their package name.
 * "_platform" is no app (a package name can't start with "_"): it is the name Health Connect
 * itself gives data no installed app wrote, such as values it works out on its own.
 */
private val APP_NAMES = mapOf(
    "com.mi.health" to "Mi Fitness",
    "com.xiaomi.wearable" to "Mi Fitness",
    "com.google.android.apps.healthdata" to "Health Connect",
    "com.google.android.apps.fitness" to "Google Fit",
    "_platform" to "Health Connect itself",
)

fun appName(packageName: String): String = APP_NAMES[packageName] ?: packageName

// toMinutesPart needs API 31; the reader runs from 28.
fun hoursAndMinutes(total: Duration): String = "${total.toHours()} h ${total.toMinutes() % 60} min"

fun weekLine(week: WeekType): String {
    if (week.amount == null || week.apps.isEmpty()) return "${week.type}: none"
    val apps = week.apps.map(::appName).distinct().sorted().joinToString()
    return "${week.type}: ${week.amount}, from $apps"
}
