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

/** The heart-rate samples one sync read, and the token to keep once the coach has them. */
class HeartRead(val samples: List<HeartSample>, val nextToken: String)

/**
 * Every Health Connect call the app makes, kept few (ADR-0070): one aggregate for steps, and
 * the changes since the last sync for heart rate. Raw history is read only on the first sync.
 */
class HealthReader(context: Context) {
    private val client = HealthConnectClient.getOrCreate(context)

    suspend fun granted(): Boolean = client.permissionController.getGrantedPermissions().containsAll(PERMISSIONS)

    /**
     * Today's and yesterday's totals, one per local day, from Health Connect's own sum. Today's
     * ends now: the coach refuses a record that ends in the future.
     */
    suspend fun steps(zone: ZoneId, today: LocalDate, now: Instant): List<DaySteps> {
        val from = today.minusDays(1).atStartOfDay()
        val groups = client.aggregateGroupByPeriod(
            AggregateGroupByPeriodRequest(
                metrics = setOf(StepsRecord.COUNT_TOTAL),
                timeRangeFilter = TimeRangeFilter.between(from, today.plusDays(1).atStartOfDay()),
                timeRangeSlicer = Period.ofDays(1),
            ),
        )
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
     * Heart rate written since [token]. Without one, or when it expired, the last 48 hours once,
     * with a token taken first so nothing written meanwhile is missed.
     */
    suspend fun heartRate(token: String?, now: Instant): HeartRead {
        if (token != null) {
            val changed = mutableListOf<HeartSample>()
            var next = token
            while (true) {
                val response = client.getChanges(next)
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
        val token = client.getChangesToken(ChangesTokenRequest(setOf(HeartRateRecord::class)))
        val found = mutableListOf<HeartSample>()
        var page: String? = null
        do {
            val response = client.readRecords(
                ReadRecordsRequest(
                    HeartRateRecord::class,
                    TimeRangeFilter.after(now.minus(48, ChronoUnit.HOURS)),
                    pageToken = page,
                ),
            )
            response.records.forEach { found += samples(it) }
            page = response.pageToken
        } while (page != null)
        return HeartRead(found, token)
    }

    private fun samples(record: HeartRateRecord): List<HeartSample> =
        record.samples.map { HeartSample(it.time, it.beatsPerMinute, record.metadata.dataOrigin.packageName) }

    companion object {
        val PERMISSIONS = setOf(
            HealthPermission.getReadPermission(StepsRecord::class),
            HealthPermission.getReadPermission(HeartRateRecord::class),
        )

        fun available(context: Context): Boolean =
            HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE
    }
}
