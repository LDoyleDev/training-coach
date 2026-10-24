import type { LoggedWorkout } from '../api'

/** The ISO day ``n`` days from ``iso``, counted on the calendar (no time zone can shift it). */
export function shift(iso: string, n: number): string {
  const at = new Date(`${iso}T12:00:00Z`)
  at.setUTCDate(at.getUTCDate() + n)
  return at.toISOString().slice(0, 10)
}

/** "Effort 6/10 · 7.29 km · 5:54/km · avg 139 bpm · max 160": what was typed with a cardio
 * log (ADR-0067), each part only when given. A ride shows its speed instead: "24.3 km/h". */
export function details(
  cardio: NonNullable<LoggedWorkout['cardio']>,
  activity?: string | null,
): string {
  const parts: string[] = []
  if (cardio.effort) parts.push(`Effort ${cardio.effort}/10`)
  if (cardio.distance_m) parts.push(`${(cardio.distance_m / 1000).toFixed(2)} km`)
  if (cardio.pace_s_per_km && activity === 'bike') {
    parts.push(`${(3600 / cardio.pace_s_per_km).toFixed(1)} km/h`)
  } else if (cardio.pace_s_per_km) {
    const seconds = cardio.pace_s_per_km
    parts.push(`${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}/km`)
  }
  if (cardio.avg_hr) parts.push(`avg ${cardio.avg_hr} bpm`)
  if (cardio.max_hr) parts.push(`max ${cardio.max_hr}`)
  return parts.join(' · ')
}
