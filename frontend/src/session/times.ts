import type { Guided } from '../api'
import { key, type Values } from './logic'

/** A longer gap between sets is a break, not a rest, and stays out of the time (ADR-0061). */
export const BREAK_SECONDS = 10 * 60
/** A rest this much longer than planned is marked on the set after it (ADR-0065). */
export const OVERRUN_SECONDS = 30
/** A set is slow when it takes this many times its exercise's other sets, and SLOW_BY more. */
const SLOW_RATIO = 1.5
const SLOW_BY = 10

/** One timed set: how long it took, whether it was much slower than its exercise's other
 * sets, and how many seconds the rest before it ran over its plan (null when it didn't). */
export type SetTime = { seconds: number; slow: boolean; overran: number | null }

/** How the session went so far, in whole minutes, and each exercise's confirmed sets in set
 * order, with their times (null for a set without times). */
export type Times = {
  minutes: number
  onSets: number
  resting: number
  breaks: number
  onBreak: number
  rows: (SetTime | null)[][]
}

/** A span of seconds in whole minutes, rounded to the nearest; at least 1 for any time at all
 * (as the saved screen counts them). */
export function wholeMinutes(seconds: number): number {
  return seconds > 0 ? Math.max(Math.round(seconds / 60), 1) : 0
}

/** "34s" under two minutes, "12 min" from there. */
export function duration(seconds: number): string {
  return seconds < 120 ? `${seconds}s` : `${Math.round(seconds / 60)} min`
}

const median = (values: number[]): number => {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

/**
 * The times of a session's confirmed sets (ADR-0061): a set runs from its screen appearing to
 * its confirm; the rest before it is the gap since the set before it was confirmed, and a gap
 * over 10 minutes is a break. A rest is planned as the `rest_seconds` of the set before it
 * (ADR-0065). Null when no set has times.
 */
export function times(session: Guided, values: Values): Times | null {
  const timed = session.order.flatMap((step) => {
    const v = values[key(step.item, step.set_no)]
    if (!v?.started_at || !v.done_at) return []
    const start = Date.parse(v.started_at)
    const done = Date.parse(v.done_at)
    if (!Number.isFinite(start) || !Number.isFinite(done)) return []
    return [{ step, start, done, seconds: Math.round(Math.max(done - start, 0) / 1000) }]
  })
  if (timed.length === 0) return null
  timed.sort((a, b) => a.start - b.start)

  let onSets = 0
  let resting = 0
  let onBreak = 0
  let breaks = 0
  const overran = new Map<string, number>()
  timed.forEach((set, n) => {
    onSets += Math.max(set.done - set.start, 0) / 1000
    if (n === 0) return
    const before = timed[n - 1]
    const gap = Math.max(set.start - before.done, 0) / 1000
    if (gap > BREAK_SECONDS) {
      breaks += 1
      onBreak += gap
      return
    }
    resting += gap
    const over = Math.round(gap - before.step.rest_seconds)
    if (over >= OVERRUN_SECONDS) overran.set(key(set.step.item, set.step.set_no), over)
  })

  const seconds = new Map(timed.map((t) => [key(t.step.item, t.step.set_no), t.seconds]))
  const rows = session.items.map((item, index) => {
    const keys = item.targets.map((_, n) => key(index, n + 1)).filter((k) => values[k])
    const own = keys.flatMap((k) => (seconds.has(k) ? [seconds.get(k) as number] : []))
    return keys.map((k): SetTime | null => {
      const took = seconds.get(k)
      if (took === undefined) return null
      const others = own.filter((_, i) => i !== own.indexOf(took))
      const usual = others.length ? median(others) : null
      return {
        seconds: took,
        slow: usual !== null && took >= usual * SLOW_RATIO && took - usual >= SLOW_BY,
        overran: overran.get(k) ?? null,
      }
    })
  })

  return {
    minutes: wholeMinutes(onSets + resting),
    onSets: wholeMinutes(onSets),
    resting: wholeMinutes(resting),
    breaks,
    onBreak: wholeMinutes(onBreak),
    rows,
  }
}

/** "So far 23 min: 9 on sets, 14 resting", and any breaks, which aren't in the total. */
export function soFar(found: Times): string {
  const breaks =
    found.breaks === 0
      ? ''
      : `, plus ${found.breaks} break${found.breaks === 1 ? '' : 's'} (${found.onBreak} min)`
  return `So far ${found.minutes} min: ${found.onSets} on sets, ${found.resting} resting${breaks}.`
}
