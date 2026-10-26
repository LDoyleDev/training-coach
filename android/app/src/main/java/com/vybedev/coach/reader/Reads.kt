package com.vybedev.coach.reader

/**
 * How many Health Connect reads one sync may make. Pure, so the limits are unit-tested (ADR-0070).
 */

/** A normal sync makes four (steps, then the changes of sleep, exercise and heart rate); a
 * week's catch-up of heart-rate changes some more. */
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

/** One change Health Connect reported for a record: written (new or edited) or deleted. */
sealed interface RecordChange<out T> {
    val id: String

    data class Written<T>(override val id: String, val record: T) : RecordChange<T>

    data class Deleted(override val id: String) : RecordChange<Nothing>
}

/**
 * What one type's read found, and the token to keep once the coach has it. [nextToken] is null
 * while the type has none yet: its first read waits for a sync with reads left. [more]: changes
 * are left for the next sync, which carries on from [nextToken]. [cut]: a history read stopped
 * at the read limit, so the rest of that day won't come across.
 */
class TypeRead<T>(
    val written: List<T>,
    val deleted: List<String>,
    val nextToken: String?,
    val more: Boolean = false,
    val cut: Boolean = false,
) {
    fun <U> flatMap(each: (T) -> List<U>) = TypeRead(written.flatMap(each), deleted, nextToken, more, cut)

    fun <U> map(each: (T) -> U) = flatMap { listOf(each(it)) }
}

/**
 * A run of changes as one per record id, the last winning, so a record written and then deleted
 * in the same batch goes only as a deletion (the ingest applies deletions first).
 */
fun <T> collapse(
    changes: List<RecordChange<T>>,
    nextToken: String?,
    more: Boolean = false,
    cut: Boolean = false,
): TypeRead<T> {
    val last = LinkedHashMap<String, RecordChange<T>>()
    changes.forEach { last.remove(it.id); last[it.id] = it }
    val written = last.values.filterIsInstance<RecordChange.Written<T>>().map { it.record }
    val deleted = last.values.filterIsInstance<RecordChange.Deleted>().map { it.id }
    return TypeRead(written, deleted, nextToken, more, cut)
}
