package com.vybedev.coach.reader

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import java.time.Instant
import java.time.LocalDate

/**
 * What one sync sends, as the JSON HC Webhook 1.9.23+ sends (ADR-0055), so the coach's ingest
 * reads it unchanged. Pure: no Android, so the unit tests cover it on the JVM.
 */

/** One local day's step total, from Health Connect's daily aggregate. */
data class DaySteps(
    val day: LocalDate,
    val start: Instant,
    val end: Instant,
    val count: Long,
    val origin: String?,
)

/** One heart-rate sample; the coach averages them per minute. */
data class HeartSample(val time: Instant, val bpm: Long, val origin: String)

const val UNKNOWN_ORIGIN = "health-connect" // what the coach assumes when a record names no app

// About 60 bytes a sample: 20,000 stay well under the coach's 5 MB limit (ADR-0055).
const val SAMPLES_PER_POST = 20_000

/**
 * The days whose total changed since it was last sent. Sending an unchanged total every sync
 * would make every sync look like new band data, and the coach's "nothing new" alert couldn't fire.
 */
fun changedDays(days: List<DaySteps>, lastSent: Map<LocalDate, Long>): List<DaySteps> =
    days.filter { it.count > 0 && lastSent[it.day] != it.count }

/** The body of one post. Types with nothing to send are left out, as HC Webhook does. */
fun payload(
    now: Instant,
    version: String,
    steps: List<DaySteps>,
    heart: List<HeartSample>,
): JsonObject = buildJsonObject {
    put("timestamp", now.toString())
    put("app_version", "tc-reader/$version")
    if (steps.isNotEmpty()) {
        put("steps", buildJsonArray {
            steps.forEach { day ->
                add(buildJsonObject {
                    put("count", day.count)
                    put("start_time", day.start.toString())
                    put("end_time", day.end.toString())
                    putJsonObject("metadata") { put("data_origin", day.origin ?: UNKNOWN_ORIGIN) }
                })
            }
        })
    }
    if (heart.isNotEmpty()) {
        put("heart_rate", buildJsonArray {
            heart.forEach { sample ->
                add(buildJsonObject {
                    put("bpm", sample.bpm)
                    put("time", sample.time.toString())
                    putJsonObject("metadata") { put("data_origin", sample.origin) }
                })
            }
        })
    }
}

/**
 * The posts one sync makes: the steps go with the first, heart rate is split so no post nears
 * the limit. Always at least one post, so an empty sync still tells the coach the phone is alive.
 */
fun posts(
    now: Instant,
    version: String,
    steps: List<DaySteps>,
    heart: List<HeartSample>,
    perPost: Int = SAMPLES_PER_POST,
): List<JsonObject> {
    val parts = heart.sortedBy { it.time }.chunked(perPost).ifEmpty { listOf(emptyList()) }
    return parts.mapIndexed { i, part -> payload(now, version, if (i == 0) steps else emptyList(), part) }
}
