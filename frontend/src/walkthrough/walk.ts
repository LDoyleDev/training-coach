/**
 * Walking a ladder (ADR-0092, "How the plan is made" 2), on this device. The first question is
 * the first open step at the suggested level, or the nearest open step below it when the ladder
 * has none there. Yes walks up, asking each next open step, until a No or the top; No walks down
 * until a Yes or the bottom. The bottom step has no question: it is where everyone starts unless
 * a Yes places them higher. Not sure counts as No; Skip this one leaves the bottom. The placement
 * is the highest Yes, with no cap going up. Locked steps are never asked.
 */

export type CanDo = 'yes' | 'no' | 'not_sure' | 'skip'

/** One step of a ladder, easiest first: its id, level, and whether it is open for this person. */
export interface Rung {
  id: number
  level: number
  open: boolean
}

export interface Walked {
  /** The index of the step to ask next, or null when the ladder is done. */
  next: number | null
  /** The index of the step the answers so far place the person on: the highest Yes, or 0. */
  placed: number
  /** The steps asked, in order, with their answers, as the answers keep them. */
  asked: [number, CanDo][]
}

/** Open steps that can be asked: every one but the bottom. */
const askable = (rungs: readonly Rung[]) => rungs.flatMap((r, i) => (i > 0 && r.open ? [i] : []))

/** The first step asked, or null when no step above the bottom is open. With no open step at
 * the level or below it, the walk starts from the bottom, so it asks the next open step up. */
export function firstAsk(rungs: readonly Rung[], level: number): number | null {
  const open = askable(rungs)
  const at = open.find((i) => rungs[i].level === level)
  if (at !== undefined) return at
  const below = open.filter((i) => rungs[i].level < level)
  if (below.length > 0)
    return below.reduce((best, i) => (rungs[i].level >= rungs[best].level ? i : best))
  return open[0] ?? null
}

const nextUp = (rungs: readonly Rung[], at: number) => askable(rungs).find((i) => i > at) ?? null
const nextDown = (rungs: readonly Rung[], at: number) =>
  askable(rungs).findLast((i) => i < at) ?? null

/** Where the answers so far leave the walk. Answers past the end of the walk are ignored. */
export function walk(rungs: readonly Rung[], level: number, answers: readonly CanDo[]): Walked {
  let next = firstAsk(rungs, level)
  let placed = 0
  let up: boolean | null = null
  const asked: [number, CanDo][] = []
  for (const answer of answers) {
    if (next === null) break
    asked.push([rungs[next].id, answer])
    if (answer === 'skip') return { next: null, placed: 0, asked }
    const yes = answer === 'yes'
    up ??= yes
    if (yes) placed = next
    next = up === yes ? (up ? nextUp(rungs, next) : nextDown(rungs, next)) : null
  }
  return { next, placed, asked }
}
