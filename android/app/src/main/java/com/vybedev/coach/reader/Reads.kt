package com.vybedev.coach.reader

/**
 * How many Health Connect reads one sync may make. Pure, so the limits are unit-tested (ADR-0070).
 */

/** A normal sync makes three or four; a week's catch-up of heart-rate changes some more. */
const val MAX_READS_PER_SYNC = 20

/**
 * The next page of a history read, or null at the last one. Health Connect on Android 12 ends
 * with an empty token, not null: 0.0.3 read "" as one more page, started the day over, and ran
 * out of quota after 202 reads (26 Oct).
 */
fun nextPage(token: String?): String? = token?.takeIf { it.isNotEmpty() }

/** A sync reached [MAX_READS_PER_SYNC]: a read that doesn't end, rather than data. */
class TooManyReads(val max: Int) : Exception("stopped after $max reads")

/** The reads one sync made, and the last, so an error can say which read it was and after how many. */
class ReadCount(private val max: Int = MAX_READS_PER_SYNC) {
    var made = 0
        private set
    var last = "none"
        private set

    /** Reads still allowed in this sync. */
    val left get() = max - made

    /** Counts one more read named [name], or throws [TooManyReads] when none is left. */
    fun next(name: String) {
        if (left <= 0) throw TooManyReads(max)
        made += 1
        last = name
    }
}
