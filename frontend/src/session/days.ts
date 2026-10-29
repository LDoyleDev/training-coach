import type { LoggedWorkout } from '../api'
import { kgText } from './logic'

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
  if (cardio.speed_kmh && activity === 'bike') {
    // The server's figure from minutes and distance, as on the card: not 3600 / a rounded pace.
    parts.push(`${cardio.speed_kmh.toFixed(1)} km/h`)
  } else if (cardio.pace_s_per_km) {
    const seconds = cardio.pace_s_per_km
    parts.push(`${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}/km`)
  }
  if (cardio.avg_hr) parts.push(`avg ${cardio.avg_hr} bpm`)
  if (cardio.max_hr) parts.push(`max ${cardio.max_hr}`)
  return parts.join(' · ')
}

type LoggedSet = LoggedWorkout['exercises'][number]['sets'][number]

/** What follows an exercise's sets, as the confirm step writes it (ADR-0072): " at 16 kg" for
 * one weight, " at 16 / 16 / 18 kg" when they differ (a dash for a set without one), and
 * nothing when no set has one. */
export function weights(sets: LoggedSet[]): string {
  return weightsOf(sets.map((set) => set.load_kg ?? null))
}

/** The same, from each set's weight in set order (null for a set without one). */
export function weightsOf(kg: (number | null)[]): string {
  const first = kg[0] ?? null
  if (kg.every((k) => k === null)) return ''
  if (first !== null && kg.every((k) => k === first)) return ` at ${kgText(first)}`
  return ` at ${kgText(kg.map((k) => (k === null ? NO_WEIGHT : String(k))).join(' / '))}`
}

const NO_WEIGHT = String.fromCharCode(0x2013) // an en dash, as on the confirm step
