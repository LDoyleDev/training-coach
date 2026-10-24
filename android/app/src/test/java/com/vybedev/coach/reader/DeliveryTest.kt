package com.vybedev.coach.reader

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Test

class DeliveryTest {
    private val three = List(3) { i -> buildJsonObject { put("part", i) } }

    /** Answers in order, and records how many posts were made. */
    private class Coach(vararg val answers: Int) {
        var posted = 0
        fun send(@Suppress("UNUSED_PARAMETER") body: JsonObject): Answer = Answer(answers[posted++], "")
    }

    @Test
    fun `every post taken means sent`() {
        val coach = Coach(200, 200, 200)
        assertEquals(Delivery.Sent(3), deliver(three, refusals = 0, coach::send))
    }

    @Test
    fun `a failure part way keeps nothing and stops posting`() {
        val coach = Coach(200, 500, 200)
        val delivery = deliver(three, refusals = 0, coach::send)
        assertEquals(Delivery.Failed(Answer(500, ""), refusals = 0), delivery)
        assertEquals(2, coach.posted)
    }

    @Test
    fun `a refusal for good is counted`() {
        val delivery = deliver(three, refusals = 1, Coach(413)::send)
        assertEquals(Delivery.Failed(Answer(413, ""), refusals = 2), delivery)
    }

    @Test
    fun `the third refusal in a row skips what is left of the batch`() {
        val delivery = deliver(three, refusals = 2, Coach(200, 422)::send)
        assertEquals(Delivery.Skipped(Answer(422, ""), dropped = 2, of = 3), delivery)
    }

    @Test
    fun `any other outcome starts the refusal count again`() {
        assertEquals(Delivery.Failed(Answer(401, ""), refusals = 0), deliver(three, refusals = 2, Coach(401)::send))
        assertEquals(Delivery.Failed(Answer(0, ""), refusals = 0), deliver(three, refusals = 2, Coach(0)::send))
    }
}
