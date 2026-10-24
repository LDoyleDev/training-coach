package com.vybedev.coach.reader

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.LocalDate

class PayloadTest {
    private val now = Instant.parse("2026-10-24T12:00:00Z")
    private val friday = DaySteps(
        LocalDate.parse("2026-10-23"),
        Instant.parse("2026-10-22T22:00:00Z"),
        Instant.parse("2026-10-23T22:00:00Z"),
        9_812,
        "com.mi.health",
    )
    private val saturday = friday.copy(
        day = LocalDate.parse("2026-10-24"),
        start = Instant.parse("2026-10-23T22:00:00Z"),
        end = now,
        count = 4_100,
    )

    private fun heart(n: Int) = List(n) { HeartSample(now.minusSeconds(60L * (n - it)), 60L + it % 40, "com.mi.health") }

    private fun parse(body: JsonObject): JsonObject = Json.parseToJsonElement(body.toString()).jsonObject

    @Test
    fun `a day is sent only when its total changed`() {
        val sent = mapOf(friday.day to 9_812L, saturday.day to 3_000L)
        assertEquals(listOf(saturday), changedDays(listOf(friday, saturday), sent))
    }

    @Test
    fun `a day with no steps is not sent`() {
        assertEquals(emptyList<DaySteps>(), changedDays(listOf(saturday.copy(count = 0)), emptyMap()))
    }

    @Test
    fun `the body has the shape the coach's ingest reads`() {
        val body = parse(payload(now, "0.0.1", listOf(saturday), heart(1)))
        assertEquals("tc-reader/0.0.1", body["app_version"]!!.jsonPrimitive.content)
        assertEquals("2026-10-24T12:00:00Z", body["timestamp"]!!.jsonPrimitive.content)
        val steps = body["steps"]!!.jsonArray.single().jsonObject
        assertEquals(4_100L, steps["count"]!!.jsonPrimitive.content.toLong())
        assertEquals("2026-10-23T22:00:00Z", steps["start_time"]!!.jsonPrimitive.content)
        assertEquals("com.mi.health", steps["metadata"]!!.jsonObject["data_origin"]!!.jsonPrimitive.content)
        val sample = body["heart_rate"]!!.jsonArray.single().jsonObject
        assertEquals(setOf("bpm", "time", "metadata"), sample.keys)
    }

    @Test
    fun `types with nothing to send are left out`() {
        val body = parse(payload(now, "0.0.1", emptyList(), emptyList()))
        assertFalse("steps" in body)
        assertFalse("heart_rate" in body)
    }

    @Test
    fun `a step record naming no app gets the coach's unknown source`() {
        val body = parse(payload(now, "0.0.1", listOf(saturday.copy(origin = null)), emptyList()))
        val origin = body["steps"]!!.jsonArray.single().jsonObject["metadata"]!!.jsonObject["data_origin"]
        assertEquals(UNKNOWN_ORIGIN, origin!!.jsonPrimitive.content)
    }

    @Test
    fun `heart rate is split across posts and the steps go with the first`() {
        val bodies = posts(now, "0.0.1", listOf(saturday), heart(5), perPost = 2).map(::parse)
        assertEquals(3, bodies.size)
        assertTrue("steps" in bodies[0])
        assertFalse("steps" in bodies[1])
        assertEquals(listOf(2, 2, 1), bodies.map { it["heart_rate"]!!.jsonArray.size })
    }

    @Test
    fun `an empty sync is still one post, so the coach hears from the phone`() {
        assertEquals(1, posts(now, "0.0.1", emptyList(), emptyList()).size)
    }

    @Test
    fun `sent totals survive being stored`() {
        val days = mapOf(friday.day to 9_812L, saturday.day to 4_100L)
        assertEquals(days, decodeSteps(encodeSteps(days)))
        assertEquals(emptyMap<LocalDate, Long>(), decodeSteps(""))
        assertEquals(emptyMap<LocalDate, Long>(), decodeSteps("not=a;day"))
        // A bad entry is dropped, the good ones kept: only that day is sent again.
        assertEquals(mapOf(friday.day to 9_812L), decodeSteps("2026-10-23=9812;2026-13-40=5;2026-10-24=x"))
    }

    @Test
    fun `only the coach's own ingest address is used`() {
        val host = "coach.example"
        assertTrue(usableAddress("https://coach.example/api/ingest/health-connect", host))
        assertFalse(usableAddress("http://coach.example/api/ingest/health-connect", host))
        assertFalse(usableAddress("HTTPS://coach.example/api/ingest/health-connect", host))
        // A look-alike that would send the secret to evil.example.
        assertFalse(usableAddress("https://coach.example@evil.example/api/ingest/health-connect", host))
        assertFalse(usableAddress("https://coach.example.evil.example/api/ingest/health-connect", host))
        assertFalse(usableAddress("https://coach.example:8443/api/ingest/health-connect", host))
        assertFalse(usableAddress("https://coach.example/api/account", host))
        assertFalse(usableAddress("https://coach.example/api/ingest/health-connect?to=x", host))
        assertFalse(usableAddress("https://coach.example/api ingest", host))
        assertFalse(usableAddress("https://", host))
        assertFalse(usableAddress("", host))
    }

    @Test
    fun `the built-in address is the coach's ingest`() {
        assertTrue(usableAddress(BuildConfig.COACH_URL, "coach.vybe-dev.com"))
    }
}
