package com.vybedev.coach.reader

import kotlinx.serialization.json.JsonObject

/**
 * Whether one sync's posts all reached the coach, and so whether its token and step totals may
 * move on. Pure, so the "nothing moves on until 2xx" rule is unit-tested (ADR-0070).
 */

const val REFUSALS_BEFORE_SKIPPING = 3 // a batch the coach refuses for good mustn't block every later sync

/** The coach's answer to one post: the HTTP status and its body, cut short for the screen. */
data class Answer(val status: Int, val body: String) {
    val ok get() = status in 200..299
    val refusedForGood get() = status == 413 || status == 422 // the same batch would be refused again
}

sealed interface Delivery {
    /** Every post got a 2xx: keep the token and the totals. */
    data class Sent(val posts: Int) : Delivery

    /** A post failed: keep nothing, so the whole sync is sent again next time. */
    data class Failed(val answer: Answer, val refusals: Int) : Delivery

    /** Refused for good too often: keep the token anyway, and the last [dropped] posts are lost. */
    data class Skipped(val answer: Answer, val dropped: Int, val of: Int) : Delivery
}

/**
 * Sends [bodies] in order until one fails. [refusals] counts the syncs in a row whose batch was
 * refused for good; any other outcome starts the count again, so refusals weeks apart never add up.
 */
fun deliver(bodies: List<JsonObject>, refusals: Int, send: (JsonObject) -> Answer): Delivery {
    bodies.forEachIndexed { i, body ->
        val answer = send(body)
        if (answer.ok) return@forEachIndexed
        if (!answer.refusedForGood) return Delivery.Failed(answer, refusals = 0)
        val count = refusals + 1
        return if (count >= REFUSALS_BEFORE_SKIPPING) {
            Delivery.Skipped(answer, dropped = bodies.size - i, of = bodies.size)
        } else {
            Delivery.Failed(answer, refusals = count)
        }
    }
    return Delivery.Sent(bodies.size)
}
