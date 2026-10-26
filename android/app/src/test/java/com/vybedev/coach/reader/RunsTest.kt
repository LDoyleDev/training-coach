package com.vybedev.coach.reader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RunsTest {
    private val needs = setOf("read-steps", "read-sleep", "background")

    @Test
    fun `a background run needs the secret and every permission`() {
        assertTrue(mayRunInBackground(true, needs + "other", needs))
        assertFalse(mayRunInBackground(false, needs, needs))
        // Reading in the background revoked: the reads would throw, so no run.
        assertFalse(mayRunInBackground(true, needs - "background", needs))
        assertFalse(mayRunInBackground(true, needs - "read-sleep", needs))
    }

    @Test
    fun `a foreground run keeps its result and no problem`() {
        assertEquals(Kept("Sent at 09:00", null), afterRun("Sent at 09:00", false, 1, 2, "Mon 09:00"))
        assertEquals(Kept("Couldn't reach the coach", null), afterRun("Couldn't reach the coach", false, 1, 1, "Mon 09:00"))
    }

    @Test
    fun `a background run that sent nothing is kept as the problem`() {
        val kept = afterRun("Health Connect's read limit was reached", true, 5, 5, "Mon 09:00")
        assertEquals("In the background, Mon 09:00: Health Connect's read limit was reached", kept.result)
        assertEquals(kept.result, kept.problem)
    }

    @Test
    fun `a skipped batch is not delivered, so a background run that ended so is kept`() {
        // Review of #375: the skip moved sentAt, and "skipped N posts" never reached the screen.
        val skipped = Delivery.Skipped(Answer(422, ""), dropped = 2, of = 3)
        assertFalse(delivered(skipped))
        assertTrue(delivered(Delivery.Sent(posts = 1)))
        assertFalse(delivered(Delivery.Failed(Answer(500, ""), refusals = 0)))
        val kept = afterRun("The coach refused this batch 3 syncs in a row", true, 5, 5, "Mon 09:00")
        assertEquals(kept.result, kept.problem)
    }

    @Test
    fun `a background run that sent leaves the earlier problem alone`() {
        val kept = afterRun("Sent at 21:00", true, 5, 6, "Mon 21:00")
        assertEquals("In the background, Mon 21:00: Sent at 21:00", kept.result)
        assertNull(kept.problem)
    }
}
