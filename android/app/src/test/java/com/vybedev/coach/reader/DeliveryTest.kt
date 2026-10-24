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

    @Test
    fun `a read stopped by leaving the screen says to keep it open`() {
        val message = readFailure("Must be in foreground to read data")
        assertEquals(true, message.contains("keep this screen open"))
    }

    @Test
    fun `the quota error keeps Health Connect's own words`() {
        // As the phone showed it on 2026-10-24 (Health Connect on Android 12).
        val said = "Request rejected. Rate limited request quota has been exceeded. Please wait " +
            "until quota has replenished before making further requests."
        assertEquals("Health Connect's read limit was reached: $said", readFailure(said))
    }

    @Test
    fun `any other refusal is shown as it came`() {
        assertEquals("Health Connect refused the read: SecurityException", readFailure("SecurityException"))
    }
}
