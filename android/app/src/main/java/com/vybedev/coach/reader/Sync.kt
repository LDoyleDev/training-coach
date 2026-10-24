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
import java.time.ZoneId

const val REFUSALS_BEFORE_SKIPPING = 3 // a batch the coach refuses for good mustn't block every later sync

/** One sync at a time, whatever starts it, so an older token never overwrites a newer one. */
object Sync {
    private val lock = Mutex()

    suspend fun run(context: Context): String = lock.withLock {
        withContext(Dispatchers.IO) { runLocked(context) }.also { Store(context).lastResult = it }
    }

    /** Posts `{"test": true}`: the coach checks the secret and stores nothing (ADR-0055). */
    suspend fun test(context: Context): String = withContext(Dispatchers.IO) {
        val store = Store(context)
        val secret = store.secret() ?: return@withContext "Enter the secret first."
        val answer = send(store.address, secret, buildJsonObject { put("test", true) })
        if (answer.ok) "Test: the coach answered ${answer.status}. Address and secret work." else describe(answer)
    }

    private suspend fun runLocked(context: Context): String {
        val store = Store(context)
        val secret = store.secret() ?: return "Enter the secret first."
        if (!usableAddress(store.address)) return "Enter the address from the coach's Account page."
        if (!HealthReader.available(context)) return "Health Connect isn't available on this phone."
        val reader = HealthReader(context)
        if (!reader.granted()) return "Allow Health Connect access first."

        val now = Instant.now()
        val zone = ZoneId.systemDefault()
        val today = LocalDate.now(zone)
        val (steps, heart) = try {
            reader.steps(zone, today, now) to reader.heartRate(store.heartToken, now)
        } catch (e: Exception) {
            // Health Connect's quota answers with an exception; show it as it came (ADR-0070 trial).
            return "Health Connect refused the read: ${e.message ?: e.javaClass.simpleName}"
        }
        val newSteps = changedDays(steps, store.sentSteps)
        val bodies = posts(now, BuildConfig.VERSION_NAME, newSteps, heart.samples)
        for (body in bodies) {
            val answer = send(store.address, secret, body)
            if (answer.ok) continue
            if (answer.status == 413 || answer.status == 422) {
                store.refusals += 1
                if (store.refusals >= REFUSALS_BEFORE_SKIPPING) {
                    keep(store, steps, heart.nextToken)
                    return "The coach refused this batch ${store.refusals} times (${answer.status}); skipped it."
                }
            }
            return describe(answer)
        }
        keep(store, steps, heart.nextToken)
        return "Sent at ${now.atZone(zone).toLocalTime().withNano(0)}: " +
            "${newSteps.size} day(s) of steps, ${heart.samples.size} heart-rate samples, " +
            "in ${bodies.size} post(s)."
    }

    /** Only after the coach took everything: the token moves on and the totals count as sent. */
    private fun keep(store: Store, steps: List<DaySteps>, token: String) {
        store.heartToken = token
        store.sentSteps = steps.associate { it.day to it.count }
        store.refusals = 0
    }

    private fun describe(answer: Answer): String = when (answer.status) {
        0 -> "Couldn't reach the coach: ${answer.body}"
        401 -> "The coach didn't accept the secret (401). Make a new one on Account > Band import."
        413 -> "The coach refused the sync as too large (413)."
        429 -> "Too many tries (429): wait 10 minutes."
        else -> "The coach answered ${answer.status}: ${answer.body}"
    }
}
