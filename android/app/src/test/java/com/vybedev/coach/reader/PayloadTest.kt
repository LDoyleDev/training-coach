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
        assertFalse("sleep" in body)
        assertFalse("exercise" in body)
        assertFalse("deleted" in body)
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

    // The night and the walk of backend/tests/api/test_ingest.py's _reader_sync: the same values,
    // so the coach's test posts what this builds.
    private val modified = Instant.parse("2026-10-11T05:10:00.123Z")
    private val night = Night(
        Instant.parse("2026-10-10T21:30:00Z"),
        Instant.parse("2026-10-11T05:00:00Z"),
        listOf(
            Stage(Instant.parse("2026-10-10T21:30:00Z"), Instant.parse("2026-10-11T01:30:00Z"), 4),
            Stage(Instant.parse("2026-10-11T01:30:00Z"), Instant.parse("2026-10-11T05:00:00Z"), 5),
        ),
        Meta("night-1", "com.mi.health", modified),
    )
    private val walk = Workout(
        Instant.parse("2026-10-10T15:00:00.250Z"),
        Instant.parse("2026-10-10T15:46:00Z"),
        79,
        Meta("walk-1", "com.mi.health", modified),
    )

    @Test
    fun `sleep goes as the coach's ingest reads it`() {
        val body = parse(payload(now, "0.0.5", emptyList(), emptyList(), Sessions(sleep = listOf(night))))
        val sent = body["sleep"]!!.jsonArray.single().jsonObject
        assertEquals("2026-10-11T05:00:00Z", sent["session_end_time"]!!.jsonPrimitive.content)
        assertEquals("27000", sent["duration_seconds"]!!.jsonPrimitive.content)
        val stages = sent["stages"]!!.jsonArray.map { it.jsonObject }
        // Stage numbers go as strings, as HC Webhook sends them; the coach counts their seconds.
        assertEquals(listOf("4", "5"), stages.map { it["stage"]!!.jsonPrimitive.content })
        assertTrue(stages[0]["stage"]!!.jsonPrimitive.isString)
        assertEquals(listOf("14400", "12600"), stages.map { it["duration_seconds"]!!.jsonPrimitive.content })
        val meta = sent["metadata"]!!.jsonObject
        assertEquals("night-1", meta["id"]!!.jsonPrimitive.content)
        assertEquals("com.mi.health", meta["data_origin"]!!.jsonPrimitive.content)
        assertEquals("2026-10-11T05:10:00.123Z", meta["last_modified_time"]!!.jsonPrimitive.content)
    }

    @Test
    fun `exercise goes with its type and times at full precision`() {
        val body = parse(payload(now, "0.0.5", emptyList(), emptyList(), Sessions(exercise = listOf(walk))))
        val sent = body["exercise"]!!.jsonArray.single().jsonObject
        assertEquals("79", sent["type"]!!.jsonPrimitive.content)
        assertTrue(sent["type"]!!.jsonPrimitive.isString)
        // The coach knows a workout by where it came from and when it started, to the nanosecond.
        assertEquals("2026-10-10T15:00:00.250Z", sent["start_time"]!!.jsonPrimitive.content)
        assertEquals("2026-10-10T15:46:00Z", sent["end_time"]!!.jsonPrimitive.content)
        assertEquals("walk-1", sent["metadata"]!!.jsonObject["id"]!!.jsonPrimitive.content)
    }

    @Test
    fun `deletions go as type and id`() {
        val gone = listOf(Removed(SLEEP, "night-0"), Removed(EXERCISE, "walk-0"))
        val body = parse(payload(now, "0.0.5", emptyList(), emptyList(), Sessions(deleted = gone)))
        val sent = body["deleted"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("sleep", "exercise"), sent.map { it["type"]!!.jsonPrimitive.content })
        assertEquals(listOf("night-0", "walk-0"), sent.map { it["id"]!!.jsonPrimitive.content })
        assertFalse("sleep" in body)
        assertFalse("exercise" in body)
    }

    @Test
    fun `a session naming no app gets the coach's unknown source`() {
        // The coach refuses an empty data_origin, which would drop the whole record.
        val unnamed = walk.copy(meta = walk.meta.copy(origin = ""))
        val body = parse(payload(now, "0.0.5", emptyList(), emptyList(), Sessions(exercise = listOf(unnamed))))
        val meta = body["exercise"]!!.jsonArray.single().jsonObject["metadata"]!!.jsonObject
        assertEquals(UNKNOWN_ORIGIN, meta["data_origin"]!!.jsonPrimitive.content)
    }

    @Test
    fun `sleep, exercise and deletions go with the first post only`() {
        val sessions = Sessions(listOf(night), listOf(walk), listOf(Removed(SLEEP, "night-0")))
        val bodies = posts(now, "0.0.5", emptyList(), heart(3), perPost = 2, sessions = sessions).map(::parse)
        assertEquals(2, bodies.size)
        assertTrue(listOf("sleep", "exercise", "deleted").all { it in bodies[0] })
        assertTrue(listOf("sleep", "exercise", "deleted").none { it in bodies[1] })
        // With no heart rate, they still go, in the one post.
        assertTrue("sleep" in posts(now, "0.0.5", emptyList(), emptyList(), sessions = sessions).single())
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
