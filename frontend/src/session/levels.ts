import type { ItemLevel } from '../api'
import { confirmText } from '../plan/ladder'

export type LevelScope = 'today' | 'from_now_on'
type Rung = ItemLevel['ladder'][number]

/** The levels shown first: one down, today's and one up (ADR-0080). */
export function nearby(level: ItemLevel): Rung[] {
  const at = level.ladder.findIndex((r) => r.id === level.step_id)
  if (at < 0) return level.ladder
  return level.ladder.slice(Math.max(0, at - 1), at + 2)
}

/** What a change did, in plain words, for the note above the set screen. */
export function levelNote(
  exercise: string,
  step: string,
  scope: LevelScope,
  warning: string | null,
): string {
  const what =
    scope === 'today'
      ? `${exercise}: ${step} for today. Your level stays as it was.`
      : `${exercise} is now on ${step}, today and from now on.`
  return `${what} ${confirmText(step)}${warning ? ` ${warning}` : ''}`
}
