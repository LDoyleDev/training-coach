package com.vybedev.coach.reader

/**
 * What a sync run leaves behind, foreground or background (Sync.kt, Background.kt). Pure, so
 * the rules are unit-tested on the JVM.
 */

/**
 * Whether a background run may sync at all. Without the secret or any permission it [needs]
 * (the reads and reading in the background) it could only fail, spending reads and noting the
 * same problem every 12 hours; the screen cancels the job the next time it opens.
 */
fun mayRunInBackground(hasSecret: Boolean, granted: Set<String>, needs: Set<String>): Boolean =
    hasSecret && granted.containsAll(needs)

/**
 * Whether a run delivered: every post got a 2xx. A batch skipped after three refusals moves the
 * tokens on too, but its data was dropped, so a background run that ended so is a problem to show.
 */
fun delivered(delivery: Delivery): Boolean = delivery is Delivery.Sent

/** A run's outcome: the result line, and the background problem to keep (null: leave it). */
data class Kept(val result: String, val problem: String?)

/**
 * After a run that said [said]: it [delivered] if the moment of the last delivery moved from
 * [sentBefore] to [sentAfter]. A background run that sent nothing (the quota, no network, a
 * crash) is kept as the problem, so the screen shows it next time even if a later run's result
 * has replaced it; a run that sent leaves any earlier problem for the screen to show.
 */
fun afterRun(said: String, background: Boolean, sentBefore: Long, sentAfter: Long, stamp: String): Kept {
    if (!background) return Kept(said, null)
    val result = "In the background, $stamp: $said"
    return Kept(result, if (sentAfter == sentBefore) result else null)
}
