import type { Standing } from '../api'
import { weightsOf } from '../session/days'
import { kgText } from '../session/logic'

export function amount(standing: Standing, value: number): string {
  if (standing.unit === 'seconds') return `${value} s`
  if (standing.unit === 'minutes') return `${value} min`
  return `${value}`
}

/** "Last 10 · 10 · 9 at 16 kg · best 12 at 12 kg": the last session at this step with its
 * weights as the confirm step writes them, and the best with its session's weight (ADR-0072).
 * Without weights, "Last 10 · 9 · best 12"; nothing logged here, "Not logged at this step yet". */
export function lastAndBest(s: Standing): string {
  const last =
    s.last.length > 0
      ? `Last ${s.last.map((v) => amount(s, v)).join(' · ')}${weightsOf(s.last_kg)}`
      : 'Not logged at this step yet'
  if (s.best_set === null) return last
  const at = s.best_kg !== null ? ` at ${kgText(s.best_kg)}` : ''
  return `${last} · best ${amount(s, s.best_set)}${at}`
}

export { trend } from '../components/trend'
