package com.vybedev.coach.reader

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** One sync at a time, whatever starts it, so an older token never overwrites a newer one. */
object Sync {
    private val lock = Mutex()

    /** A sync from Sync now or, with [background], from WorkManager (Background.kt). */
    suspend fun run(context: Context, background: Boolean = false): String = lock.withLock {
        val store = Store(context)
        val before = store.sentAt
        val said = withContext(Dispatchers.IO) { runLocked(context) }
        keep(store, afterRun(said, background, before, store.sentAt, stamp()))
    }

    /** A background run that failed outright: its error waits for the screen like any other. */
    fun backgroundFailed(context: Context, error: Exception) {
        val said = "Failed: ${error.message ?: error.javaClass.simpleName}"
        keep(Store(context), afterRun(said, background = true, sentBefore = 0, sentAfter = 0, stamp = stamp()))
    }

    private fun keep(store: Store, kept: Kept): String {
        store.lastResult = kept.result
        kept.problem?.let { store.backgroundProblem = it }
        return kept.result
    }

    private fun stamp(): String = LocalDateTime.now().format(DateTimeFormatter.ofPattern("EEE HH:mm", Locale.ENGLISH))

    /** "In Health Connect, last 7 days": four aggregate reads, only when the person taps it. */
    suspend fun week(context: Context): String = withContext(Dispatchers.IO) {
        if (!HealthReader.available(context)) return@withContext "Health Connect isn't available on this phone."
        val reader = HealthReader(context)
        if (reader.missing().isNotEmpty()) return@withContext "Allow Health Connect access first."
        try {
            "In Health Connect, last 7 days:\n" + reader.lastWeek(Instant.now()).joinToString("\n", transform = ::weekLine)
        } catch (e: Exception) {
            readFailure(e.message ?: e.javaClass.simpleName) + " (at ${reader.reads.last})"
        }
    }

    /** Posts `{"test": true}`: the coach checks the secret and stores nothing (ADR-0055). */
    suspend fun test(context: Context): String = withContext(Dispatchers.IO) {
        val store = Store(context)
        val secret = store.secret() ?: return@withContext "Enter the secret first."
        val answer = send(secret, buildJsonObject { put("test", true) })
        if (answer.ok) "Test: the coach answered ${answer.status}. The secret works." else describe(answer)
    }

    private suspend fun runLocked(context: Context): String {
        val store = Store(context)
        val secret = store.secret() ?: return "Enter the secret first."
        if (!HealthReader.available(context)) return "Health Connect isn't available on this phone."
        val reader = HealthReader(context)
        val missing = reader.missing()
        if (missing.isNotEmpty()) return "Allow Health Connect access first (${missing.values.joinToString()})."

        val now = Instant.now()
        val zone = ZoneId.systemDefault()
        val today = LocalDate.now(zone)
        // Heart rate last: it is the heaviest, so a catch-up of it can't leave sleep unread.
        val read = try {
            Read(
                steps = reader.steps(zone, today, now),
                sleep = reader.sleep(store.sleepToken, now),
                exercise = reader.exercise(store.exerciseToken, now),
                heart = reader.heartRate(store.heartToken, now),
            )
        } catch (e: TooManyReads) {
            return "Stopped after ${e.max} Health Connect reads (at ${reader.reads.last}), so as not " +
                "to use up its quota. Nothing was sent."
        } catch (e: Exception) {
            // Health Connect's quota answers with an exception; show it as it came (ADR-0070 trial).
            return readFailure(e.message ?: e.javaClass.simpleName) +
                " (at ${reader.reads.last}, read ${reader.reads.made} of this sync)"
        }
        val newSteps = changedDays(read.steps, store.sentSteps)
        val sessions = Sessions(
            sleep = read.sleep.written,
            exercise = read.exercise.written,
            deleted = read.sleep.deleted.map { Removed(SLEEP, it) } + read.exercise.deleted.map { Removed(EXERCISE, it) },
        )
        val bodies = posts(now, BuildConfig.VERSION_NAME, newSteps, read.heart.written, sessions = sessions)
        return when (val delivery = deliver(bodies, store.refusals) { send(secret, it) }) {
            is Delivery.Sent -> {
                keep(store, read)
                "Sent at ${now.atZone(zone).toLocalTime().withNano(0)}, in ${delivery.posts} post(s), " +
                    "${reader.reads.made} read(s).\n" + sent(newSteps.size, read) + later(read)
            }
            is Delivery.Failed -> {
                store.refusals = delivery.refusals
                describe(delivery.answer)
            }
            is Delivery.Skipped -> {
                keep(store, read)
                "The coach refused this batch $REFUSALS_BEFORE_SKIPPING syncs in a row " +
                    "(${delivery.answer.status}), so it was skipped: the last ${delivery.dropped} of " +
                    "${delivery.of} post(s) won't be sent" +
                    (if (delivery.dropped == delivery.of) ", steps, sleep and exercise included" else "") +
                    ". Later data is sent as usual."
            }
        }
    }

    /** What one sync read, per type. */
    private class Read(
        val steps: List<DaySteps>,
        val sleep: TypeRead<Night>,
        val exercise: TypeRead<Workout>,
        val heart: TypeRead<HeartSample>,
    ) {
        val types get() = listOf("sleep" to sleep, "exercise" to exercise, "heart rate" to heart)
    }

    /** Per type, what was sent: the result line on the screen. */
    private fun sent(days: Int, read: Read): String = listOf(
        "Steps: $days day(s)",
        "Sleep: ${read.sleep.written.size} night(s)" + removed(read.sleep),
        "Exercise: ${read.exercise.written.size} workout(s)" + removed(read.exercise),
        "Heart rate: ${read.heart.written.size} sample(s)",
    ).joinToString("\n")

    private fun removed(read: TypeRead<*>) = if (read.deleted.isEmpty()) "" else ", ${read.deleted.size} removed"

    private fun later(read: Read): String {
        val more = read.types.filter { it.second.more }.map { it.first }
        val cut = read.types.filter { it.second.cut }.map { it.first }
        return (if (more.isEmpty()) "" else "\nMore ${more.joinToString(" and ")} comes with the next sync.") +
            (if (cut.isEmpty()) "" else "\nHistory of ${cut.joinToString(" and ")} stopped at " +
                "$MAX_READS_PER_SYNC reads, so part of that day won't come across; later data comes as usual.")
    }

    /** Only after the coach took everything: the tokens move on and the totals count as sent. */
    private fun keep(store: Store, read: Read) {
        store.sleepToken = read.sleep.nextToken
        store.exerciseToken = read.exercise.nextToken
        store.heartToken = read.heart.nextToken
        store.sentSteps = read.steps.associate { it.day to it.count }
        store.sentAt = System.currentTimeMillis()
        store.refusals = 0
    }

    private fun describe(answer: Answer): String = when (answer.status) {
        0 -> "Couldn't reach the coach: ${answer.body}"
        401 -> "The coach didn't accept the secret (401). Make a new one on Account > Band import."
        413 -> "The coach refused the sync as too large (413)."
        422 -> "The coach couldn't read the sync (422)."
        429 -> "Too many tries (429): wait 10 minutes."
        else -> "The coach answered ${answer.status}: ${answer.body}"
    }
}
