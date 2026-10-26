package com.vybedev.coach.reader

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import java.time.Duration
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

/** The payload keys of the types whose deletions the coach applies, as `deleted[].type`. */
const val SLEEP = "sleep"
const val EXERCISE = "exercise"

/** Who wrote a record and when, with its Health Connect id, so an edit replaces it on the coach. */
data class Meta(val id: String, val origin: String, val modified: Instant)

/** A part of a night: AndroidX's STAGE_TYPE_* number (4 light, 5 deep, 6 REM, 1 awake). */
data class Stage(val start: Instant, val end: Instant, val stage: Int)

/** One sleep session as Health Connect has it. */
data class Night(val start: Instant, val end: Instant, val stages: List<Stage>, val meta: Meta)

/** One exercise session: AndroidX's EXERCISE_TYPE_* number (79 walking, 56 running). */
data class Workout(val start: Instant, val end: Instant, val type: Int, val meta: Meta)

/** A record deleted from Health Connect: [type] is [SLEEP] or [EXERCISE]. */
data class Removed(val type: String, val id: String)

/** Sleep, exercise and deletions: a few records a day, so they go with the first post. */
data class Sessions(
    val sleep: List<Night> = emptyList(),
    val exercise: List<Workout> = emptyList(),
    val deleted: List<Removed> = emptyList(),
)

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
    sessions: Sessions = Sessions(),
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
    if (sessions.sleep.isNotEmpty()) {
        put(SLEEP, buildJsonArray {
            sessions.sleep.forEach { night ->
                add(buildJsonObject {
                    // The coach takes the start as the end less the length.
                    put("session_end_time", night.end.toString())
                    put("duration_seconds", seconds(night.start, night.end))
                    put("stages", buildJsonArray {
                        night.stages.forEach { stage ->
                            add(buildJsonObject {
                                put("stage", stage.stage.toString()) // a string, as HC Webhook sends it
                                put("start_time", stage.start.toString())
                                put("end_time", stage.end.toString())
                                put("duration_seconds", seconds(stage.start, stage.end))
                            })
                        }
                    })
                    put("metadata", metadata(night.meta))
                })
            }
        })
    }
    if (sessions.exercise.isNotEmpty()) {
        put(EXERCISE, buildJsonArray {
            sessions.exercise.forEach { workout ->
                add(buildJsonObject {
                    put("type", workout.type.toString())
                    put("start_time", workout.start.toString())
                    put("end_time", workout.end.toString())
                    put("duration_seconds", seconds(workout.start, workout.end))
                    put("metadata", metadata(workout.meta))
                })
            }
        })
    }
    if (sessions.deleted.isNotEmpty()) {
        put("deleted", buildJsonArray {
            sessions.deleted.forEach { add(buildJsonObject { put("type", it.type); put("id", it.id) }) }
        })
    }
}

private fun seconds(start: Instant, end: Instant): Long = Duration.between(start, end).seconds

// The coach refuses a session whose data_origin is empty, so an unnamed app gets its default.
private fun metadata(meta: Meta) = buildJsonObject {
    put("data_origin", meta.origin.ifEmpty { UNKNOWN_ORIGIN })
    put("id", meta.id)
    put("last_modified_time", meta.modified.toString())
}

/**
 * The posts one sync makes: the steps and [sessions] go with the first, heart rate is split so
 * no post nears the limit. Always at least one post, so an empty sync still tells the coach the
 * phone is alive.
 */
fun posts(
    now: Instant,
    version: String,
    steps: List<DaySteps>,
    heart: List<HeartSample>,
    perPost: Int = SAMPLES_PER_POST,
    sessions: Sessions = Sessions(),
): List<JsonObject> {
    val parts = heart.sortedBy { it.time }.chunked(perPost).ifEmpty { listOf(emptyList()) }
    return parts.mapIndexed { i, part ->
        if (i == 0) payload(now, version, steps, part, sessions) else payload(now, version, emptyList(), part)
    }
}
