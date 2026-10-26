package com.vybedev.coach.reader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
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

    @Test
    fun `changes come as one per record, the last winning`() {
        val read = collapse(
            listOf(
                RecordChange.Written("a", "night a"),
                RecordChange.Written("b", "walk b"),
                RecordChange.Written("a", "night a, edited"),
                RecordChange.Written("c", "walk c"),
                RecordChange.Deleted("c"),
                RecordChange.Deleted("d"),
            ),
            nextToken = "token-2",
        )
        assertEquals(listOf("walk b", "night a, edited"), read.written)
        // Written and deleted in one batch: only the deletion goes, which the ingest applies first.
        assertEquals(listOf("c", "d"), read.deleted)
        assertEquals("token-2", read.nextToken)
    }

    @Test
    fun `a type's read keeps its token and flags through a map`() {
        val read = collapse(listOf(RecordChange.Written("a", 2)), nextToken = null, more = true)
        val mapped = read.flatMap { List(it) { n -> "sample $n" } }
        assertEquals(listOf("sample 0", "sample 1"), mapped.written)
        assertNull(mapped.nextToken)
        assertTrue(mapped.more)
        assertFalse(mapped.cut)
    }
}
