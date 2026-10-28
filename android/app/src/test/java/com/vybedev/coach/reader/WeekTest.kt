package com.vybedev.coach.reader

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.Duration

class WeekTest {
    @Test
    fun `a type says how much there is and which apps wrote it, by name`() {
        val sleep = WeekType("Sleep", hoursAndMinutes(Duration.ofMinutes(2_890)), setOf("com.mi.health", "org.example"))
        assertEquals("Sleep: 48 h 10 min, from Mi Fitness, org.example", weekLine(sleep))
    }

    @Test
    fun `two packages of one app name it once`() {
        val steps = WeekType("Steps", "54,321 steps", setOf("com.mi.health", "com.xiaomi.wearable"))
        assertEquals("Steps: 54,321 steps, from Mi Fitness", weekLine(steps))
    }

    @Test
    fun `a type Health Connect has none of says so`() {
        assertEquals("Exercise: none", weekLine(WeekType("Exercise", null, emptySet())))
        assertEquals("Exercise: none", weekLine(WeekType("Exercise", "0 h 0 min", emptySet())))
    }

    @Test
    fun `an unknown app goes by its package name`() {
        assertEquals("org.example", appName("org.example"))
        assertEquals("Health Connect", appName("com.google.android.apps.healthdata"))
    }

    @Test
    fun `data no app wrote is Health Connect's own, not a package called _platform`() {
        val exercise = WeekType("Exercise", "2 h 15 min", setOf("_platform", "com.mi.health"))
        assertEquals("Exercise: 2 h 15 min, from Health Connect itself, Mi Fitness", weekLine(exercise))
    }
}
