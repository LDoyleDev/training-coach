package com.vybedev.coach.reader

import android.content.Context
import java.time.LocalDate

/** What the app keeps between syncs, in its own preferences (never backed up: no_backup.xml). */
class Store(context: Context) {
    private val prefs = context.getSharedPreferences("reader", Context.MODE_PRIVATE)

    var address: String
        get() = prefs.getString("address", "").orEmpty()
        set(value) = prefs.edit().putString("address", value.trim()).apply()

    val hasSecret get() = prefs.contains("secret")

    fun saveSecret(secret: String) = prefs.edit().putString("secret", SecretBox.seal(secret.trim())).apply()

    fun secret(): String? = prefs.getString("secret", null)?.let(SecretBox::open)

    /** Health Connect's changes token for heart rate: null until the first good sync. */
    var heartToken: String?
        get() = prefs.getString("heart_token", null)
        set(value) = prefs.edit().putString("heart_token", value).apply()

    /** Each recent day's step total as last sent, so an unchanged day isn't sent again. */
    var sentSteps: Map<LocalDate, Long>
        get() = decodeSteps(prefs.getString("sent_steps", "").orEmpty())
        set(value) = prefs.edit().putString("sent_steps", encodeSteps(value)).apply()

    /** How many syncs in a row the coach refused for good (413 or 422). */
    var refusals: Int
        get() = prefs.getInt("refusals", 0)
        set(value) = prefs.edit().putInt("refusals", value).apply()

    /** The last sync's outcome, as shown on the screen. */
    var lastResult: String
        get() = prefs.getString("last_result", "No sync yet.").orEmpty()
        set(value) = prefs.edit().putString("last_result", value).apply()
}

fun encodeSteps(days: Map<LocalDate, Long>): String =
    days.entries.sortedBy { it.key }.joinToString(";") { "${it.key}=${it.value}" }

fun decodeSteps(text: String): Map<LocalDate, Long> =
    text.split(";").mapNotNull { part ->
        val (day, count) = part.split("=").takeIf { it.size == 2 } ?: return@mapNotNull null
        runCatching { LocalDate.parse(day) to count.toLong() }.getOrNull()
    }.toMap()
