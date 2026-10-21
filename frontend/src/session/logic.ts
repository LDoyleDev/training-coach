import type { Done, Guided, GuidedItem, Kept } from '../api'

/** One confirmed set as the screen holds it: `split` means left and right differ. A confirmed
 * set also has when its screen appeared and when it was confirmed (ADR-0061). */
export type Value = {
  left: number
  right: number
  split: boolean
  started_at?: string
  done_at?: string
}
export type Values = Record<string, Value>

export const key = (item: number, setNo: number) => `${item}:${setNo}`

/** Values kept on the server, as the screen holds them. */
export function fromKept(kept: Kept | null | undefined): Values {
  const values: Values = {}
  for (const d of kept?.sets ?? []) {
    const right = d.right ?? d.left
    const value: Value = { left: d.left, right, split: right !== d.left }
    if (d.started_at && d.done_at)
      Object.assign(value, { started_at: d.started_at, done_at: d.done_at })
    values[key(d.item, d.set_no)] = value
  }
  return values
}

/** The confirmed sets to keep, in work order. `right` only where an exercise is one-sided
 * and the sides differ. */
export function toDone(session: Guided, values: Values): Done[] {
  return session.order.flatMap((s) => {
    const v = values[key(s.item, s.set_no)]
    if (!v) return []
    const sided = session.items[s.item].per_side && v.split
    const done: Done = {
      item: s.item,
      set_no: s.set_no,
      left: v.left,
      right: sided ? v.right : null,
    }
    if (v.started_at && v.done_at)
      Object.assign(done, { started_at: v.started_at, done_at: v.done_at })
    return [done]
  })
}

/** A set as confirmed now: with the times of its first confirm, or else from when its screen
 * appeared (`shownAt`) until now. A set fixed with Back keeps its first times (ADR-0061). */
export function timed(value: Value, shownAt: number, now: number): Value {
  if (value.started_at && value.done_at) return value
  const started = Math.min(shownAt, now)
  return {
    ...value,
    started_at: new Date(started).toISOString(),
    done_at: new Date(now).toISOString(),
  }
}

/** The value a set starts at: what was confirmed, else its target. */
export function valueFor(values: Values, item: number, setNo: number, target: number): Value {
  return values[key(item, setNo)] ?? { left: target, right: target, split: false }
}

/** How much one tap of + or − changes a value. */
export function stepOf(item: GuidedItem): number {
  return item.unit === 'reps' ? 1 : 5
}

export function unitText(item: GuidedItem, value: number): string {
  if (item.unit === 'seconds') return `${value} s`
  if (item.unit === 'minutes') return `${value} min`
  return `${value}`
}

export function versus(value: number, target: number): string {
  if (value === target) return 'on target'
  return value > target ? `${value - target} over` : `${target - value} under`
}

/** Each exercise's sets as done and as targeted, for Check and save. */
export function summary(session: Guided, values: Values) {
  return session.items.map((item, index) => {
    const sets = item.targets.map((_, n) => values[key(index, n + 1)] ?? null)
    const done = sets
      .filter((v): v is Value => v !== null)
      .map((v) => (item.per_side && v.split ? `${v.left}/${v.right}` : unitText(item, v.left)))
    const hit = sets.every(
      (v, n) => v !== null && v.left >= item.targets[n] && v.right >= item.targets[n],
    )
    return {
      name: item.name,
      target: item.targets.map((t) => unitText(item, t)).join(' · '),
      done: done.length ? done.join(' · ') : 'not done',
      hit,
    }
  })
}

/** The other exercise of a set's pair, if it has one. */
export function partnerOf(session: Guided, item: number): GuidedItem | null {
  const pair = session.items[item].pair
  if (pair === null) return null
  return session.items.find((other, i) => i !== item && other.pair === pair) ?? null
}

/** The cardio exercises logged in one step (ux-flow-plan A1): HIIT counts rounds, the others
 * minutes. */
export const CARDIO: string[] = ['zone2', 'moderate-cardio', 'hiit']

/** "Thu 08 Oct" for an ISO date, read as a calendar day (no time zone shift). */
export function dayText(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  })
}

/** Today and the 14 days before it, as ISO dates, today first. */
export function recentDays(now: Date = new Date()): string[] {
  return Array.from({ length: 15 }, (_, n) => {
    const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - n)
    const pad = (v: number) => String(v).padStart(2, '0')
    return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
  })
}
