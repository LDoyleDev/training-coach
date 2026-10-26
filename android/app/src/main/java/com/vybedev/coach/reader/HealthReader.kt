package com.vybedev.coach.reader

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.aggregate.AggregateMetric
import androidx.health.connect.client.changes.DeletionChange
import androidx.health.connect.client.changes.UpsertionChange
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.Record
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateGroupByPeriodRequest
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ChangesTokenRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.LocalDate
import java.time.Period
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import kotlin.reflect.KClass

/**
 * Every Health Connect call the app makes, kept few (ADR-0070): one aggregate for steps, and
 * the changes since the last sync for sleep, exercise and heart rate, one token per type. Raw
 * history is read only on a type's first sync.
 */
class HealthReader(context: Context) {
    private val client = HealthConnectClient.getOrCreate(context)

    /** Health Connect reads made by this reader, at most MAX_READS_PER_SYNC, for the trial
     * (ADR-0070): a quota error says which read hit it and after how many. */
    val reads = ReadCount()

    private suspend fun <T> read(name: String, call: suspend () -> T): T {
        reads.next(name)
        return call()
    }

    /** Every Health Connect permission the reader has (no read of health data). */
    suspend fun granted(): Set<String> = client.permissionController.getGrantedPermissions()

    /** The read permissions not granted yet, by what the screen calls them. */
    suspend fun missing(): Map<String, String> {
        val granted = granted()
        return READS.filterKeys { it !in granted }
    }

    /**
     * The last 7 days per type, from one aggregate each: four reads, only when the person asks.
     * An aggregate's data origins are the apps that wrote the type.
     */
    suspend fun lastWeek(now: Instant): List<WeekType> {
        val range = TimeRangeFilter.between(now.minus(7, ChronoUnit.DAYS), now)
        suspend fun <T : Any> week(type: String, metric: AggregateMetric<T>, amount: (T) -> String): WeekType {
            val result = read("$type, last 7 days") { client.aggregate(AggregateRequest(setOf(metric), range)) }
            return WeekType(type, result[metric]?.let(amount), result.dataOrigins.map { it.packageName }.toSet())
        }
        return listOf(
            week("Steps", StepsRecord.COUNT_TOTAL) { "%,d steps".format(it) },
            week("Heart rate", HeartRateRecord.MEASUREMENTS_COUNT) { "%,d samples".format(it) },
            week("Sleep", SleepSessionRecord.SLEEP_DURATION_TOTAL) { hoursAndMinutes(it) },
            week("Exercise", ExerciseSessionRecord.EXERCISE_DURATION_TOTAL) { hoursAndMinutes(it) },
        )
    }

    /**
     * Today's and yesterday's totals, one per local day, from Health Connect's own sum. Today's
     * ends now: the coach refuses a record that ends in the future.
     */
    suspend fun steps(zone: ZoneId, today: LocalDate, now: Instant): List<DaySteps> {
        val from = today.minusDays(1).atStartOfDay()
        val groups = read("steps totals") { client.aggregateGroupByPeriod(
            AggregateGroupByPeriodRequest(
                metrics = setOf(StepsRecord.COUNT_TOTAL),
                timeRangeFilter = TimeRangeFilter.between(from, today.plusDays(1).atStartOfDay()),
                timeRangeSlicer = Period.ofDays(1),
            ),
        ) }
        return groups.mapNotNull { group ->
            val count = group.result[StepsRecord.COUNT_TOTAL] ?: return@mapNotNull null
            DaySteps(
                day = group.startTime.toLocalDate(),
                start = group.startTime.atZone(zone).toInstant(),
                end = minOf(group.endTime.atZone(zone).toInstant(), now),
                count = count,
                origin = group.result.dataOrigins.firstOrNull()?.packageName,
            )
        }
    }

    suspend fun sleep(token: String?, now: Instant): TypeRead<Night> =
        changes(SleepSessionRecord::class, "sleep", token, now).map { record ->
            Night(
                record.startTime,
                record.endTime,
                record.stages.map { Stage(it.startTime, it.endTime, it.stage) },
                meta(record),
            )
        }

    suspend fun exercise(token: String?, now: Instant): TypeRead<Workout> =
        changes(ExerciseSessionRecord::class, "exercise", token, now).map { record ->
            Workout(record.startTime, record.endTime, record.exerciseType, meta(record))
        }

    /** Heart rate as raw samples; its deletions are dropped, as the coach keeps it per minute. */
    suspend fun heartRate(token: String?, now: Instant): TypeRead<HeartSample> =
        changes(HeartRateRecord::class, "heart-rate", token, now).flatMap { record ->
            record.samples.map { HeartSample(it.time, it.beatsPerMinute, record.metadata.dataOrigin.packageName) }
        }

    /**
     * [type]'s records written or deleted since [token], one change per record. Without a token,
     * or when it expired, the last FIRST_SYNC_HOURS once, with a token taken first so nothing
     * written meanwhile is missed. Changes that would take more reads than are left wait for
     * the next sync.
     */
    private suspend fun <R : Record> changes(type: KClass<R>, name: String, token: String?, now: Instant): TypeRead<R> {
        if (token == null) return fromHistory(type, name, now)
        val found = mutableListOf<RecordChange<R>>()
        var next: String = token
        while (true) {
            if (reads.left <= 0) return collapse(found, next, more = true)
            val response = read("$name changes") { client.getChanges(next) }
            if (response.changesTokenExpired) return fromHistory(type, name, now)
            response.changes.forEach { change ->
                if (change is UpsertionChange && type.java.isInstance(change.record)) {
                    found += RecordChange.Written(change.record.metadata.id, type.java.cast(change.record))
                } else if (change is DeletionChange) {
                    found += RecordChange.Deleted(change.recordId)
                }
            }
            next = response.nextChangesToken
            if (!response.hasMore) return collapse(found, next)
        }
    }

    private suspend fun <R : Record> fromHistory(type: KClass<R>, name: String, now: Instant): TypeRead<R> {
        // A token and a page at least: without them the type waits for the next sync, tokenless.
        if (reads.left < 2) return TypeRead(emptyList(), emptyList(), null, more = true)
        val token = read("$name changes token") { client.getChangesToken(ChangesTokenRequest(setOf(type))) }
        val found = mutableListOf<RecordChange<R>>()
        var page: String? = null
        do {
            // At the limit, send what was read and keep the token: failing would leave no token,
            // and every later sync would spend the same reads again (review of #370).
            if (reads.left <= 0) return collapse(found, token, cut = true)
            // The largest page Health Connect allows, so the first sync takes as few reads as it can.
            val response = read("$name history") {
                client.readRecords(
                    ReadRecordsRequest(
                        type,
                        TimeRangeFilter.after(now.minus(FIRST_SYNC_HOURS, ChronoUnit.HOURS)),
                        pageSize = 5_000,
                        pageToken = page,
                    ),
                )
            }
            response.records.forEach { found += RecordChange.Written(it.metadata.id, it) }
            page = nextPage(response.pageToken)
        } while (page != null)
        return collapse(found, token)
    }

    private fun meta(record: Record) = record.metadata.let {
        Meta(it.id, it.dataOrigin.packageName, it.lastModifiedTime)
    }

    companion object {
        const val FIRST_SYNC_HOURS = 24L // of history on a type's first sync: a day, to spend little quota

        /** What the reader may read, and nothing else (ADR-0070), by what the screen calls it. */
        val READS = mapOf(
            HealthPermission.getReadPermission(StepsRecord::class) to "steps",
            HealthPermission.getReadPermission(HeartRateRecord::class) to "heart rate",
            HealthPermission.getReadPermission(SleepSessionRecord::class) to "sleep",
            HealthPermission.getReadPermission(ExerciseSessionRecord::class) to "exercise",
        )
        val PERMISSIONS = READS.keys

        fun available(context: Context): Boolean =
            HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE
    }
}
