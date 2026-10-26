package com.vybedev.coach.reader

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.changes.UpsertionChange
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateGroupByPeriodRequest
import androidx.health.connect.client.request.ChangesTokenRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.LocalDate
import java.time.Period
import java.time.ZoneId
import java.time.temporal.ChronoUnit

/**
 * The heart-rate samples one sync read, and the token to keep once the coach has them. [more]:
 * changes are left for the next sync, which carries on from [nextToken]. [cut]: a history read
 * stopped at the read limit, so the rest of that day won't come across.
 */
class HeartRead(
    val samples: List<HeartSample>,
    val nextToken: String,
    val more: Boolean = false,
    val cut: Boolean = false,
)

/**
 * Every Health Connect call the app makes, kept few (ADR-0070): one aggregate for steps, and
 * the changes since the last sync for heart rate. Raw history is read only on the first sync.
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

    suspend fun granted(): Boolean = client.permissionController.getGrantedPermissions().containsAll(PERMISSIONS)

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

    /**
     * Heart rate written since [token]. Without one, or when it expired, the last FIRST_SYNC_HOURS once,
     * with a token taken first so nothing written meanwhile is missed. Changes that would take
     * more reads than are left wait for the next sync.
     */
    suspend fun heartRate(token: String?, now: Instant): HeartRead {
        if (token != null) {
            val changed = mutableListOf<HeartSample>()
            var next: String = token
            while (true) {
                if (reads.left <= 0) return HeartRead(changed, next, more = true)
                val response = read("heart-rate changes") { client.getChanges(next) }
                if (response.changesTokenExpired) return fromHistory(now)
                response.changes.filterIsInstance<UpsertionChange>()
                    .mapNotNull { it.record as? HeartRateRecord }
                    .forEach { changed += samples(it) }
                next = response.nextChangesToken
                if (!response.hasMore) return HeartRead(changed, next)
            }
        }
        return fromHistory(now)
    }

    private suspend fun fromHistory(now: Instant): HeartRead {
        val token = read("changes token") { client.getChangesToken(ChangesTokenRequest(setOf(HeartRateRecord::class))) }
        val found = mutableListOf<HeartSample>()
        var page: String? = null
        do {
            // At the limit, send what was read and keep the token: failing would leave no token,
            // and every later sync would spend the same reads again (review of #370).
            if (reads.left <= 0) return HeartRead(found, token, cut = true)
            // The largest page Health Connect allows, so the first sync takes as few reads as it can.
            val response = read("heart-rate history") {
                client.readRecords(
                    ReadRecordsRequest(
                        HeartRateRecord::class,
                        TimeRangeFilter.after(now.minus(FIRST_SYNC_HOURS, ChronoUnit.HOURS)),
                        pageSize = 5_000,
                        pageToken = page,
                    ),
                )
            }
            response.records.forEach { found += samples(it) }
            page = nextPage(response.pageToken)
        } while (page != null)
        return HeartRead(found, token)
    }

    private fun samples(record: HeartRateRecord): List<HeartSample> =
        record.samples.map { HeartSample(it.time, it.beatsPerMinute, record.metadata.dataOrigin.packageName) }

    companion object {
        const val FIRST_SYNC_HOURS = 24L // of history on a first sync: a day, to spend little quota

        val PERMISSIONS = setOf(
            HealthPermission.getReadPermission(StepsRecord::class),
            HealthPermission.getReadPermission(HeartRateRecord::class),
        )

        fun available(context: Context): Boolean =
            HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE
    }
}
