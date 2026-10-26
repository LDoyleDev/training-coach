package com.vybedev.coach.reader

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.HealthConnectFeatures
import androidx.health.connect.client.permission.HealthPermission
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/**
 * The background sync (ADR-0070, spec "Syncs when it can"): WorkManager about twice a day, only
 * where the installed Health Connect lets apps read in the background. No exact alarm and no
 * foreground service, which Android 12 and MIUI restrict; WorkManager picks a time that suits
 * the phone, so a sync can come some hours late.
 */
object Background {
    private const val WORK = "sync"
    const val EVERY_HOURS = 12L

    val PERMISSION = HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND

    /** Whether this phone's Health Connect lets apps read in the background: its version decides. */
    fun supported(context: Context): Boolean =
        HealthReader.available(context) &&
            HealthConnectClient.getOrCreate(context).features.getFeatureStatus(
                HealthConnectFeatures.FEATURE_READ_HEALTH_DATA_IN_BACKGROUND,
            ) == HealthConnectFeatures.FEATURE_STATUS_AVAILABLE

    /** Keeps the twice-daily sync scheduled while it may run, and cancels it otherwise. */
    fun schedule(context: Context, allowed: Boolean) {
        val work = WorkManager.getInstance(context)
        if (!allowed) {
            work.cancelUniqueWork(WORK)
            return
        }
        val request = PeriodicWorkRequestBuilder<SyncWorker>(EVERY_HOURS, TimeUnit.HOURS)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        // KEEP: opening the screen doesn't restart the 12 hours.
        work.enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.KEEP, request)
    }
}

/** One background sync, under the same lock as Sync now. */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        Sync.run(applicationContext, background = true)
        // Its outcome is on the screen; a failed one is sent again with the next run, not retried
        // at once, so a quota error doesn't spend more quota.
        return Result.success()
    }
}
