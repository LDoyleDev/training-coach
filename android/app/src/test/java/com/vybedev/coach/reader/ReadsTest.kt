package com.vybedev.coach.reader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class ReadsTest {
    @Test
    fun `an empty page token is the last page`() {
        // Health Connect on Android 12 ends a read with "", which 0.0.3 took as one more page.
        assertNull(nextPage(""))
        assertNull(nextPage(null))
        assertEquals("page-2", nextPage("page-2"))
    }

    @Test
    fun `a sync stops at its read limit and names the last read`() {
        val reads = ReadCount(max = 3)
        repeat(3) { reads.next("heart-rate history") }
        assertEquals(0, reads.left)
        val stopped = assertThrows(TooManyReads::class.java) { reads.next("heart-rate history") }
        assertEquals(3, stopped.max)
        assertEquals(3, reads.made)
        assertEquals("heart-rate history", reads.last)
    }

    @Test
    fun `reads left counts down from the limit`() {
        val reads = ReadCount()
        reads.next("steps totals")
        assertEquals(MAX_READS_PER_SYNC - 1, reads.left)
        assertEquals("steps totals", reads.last)
    }
}
