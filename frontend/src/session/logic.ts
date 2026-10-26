import type { Done, Guided, GuidedItem, Kept } from '../api'

/** One confirmed set as the screen holds it: `split` means left and right differ. A confirmed
 * set also has when its screen appeared and when it was confirmed (ADR-0061), and on a loaded
 * step its weight (ADR-0072). */
export type Value = {
  left: number
  right: number
  split: boolean
  started_at?: string
  done_at?: string
  load_kg?: number
}
export type Values = Record<string, Value>

export const key = (item: number, setNo: number) => `${item}:${setNo}`

/** "Switch to Rows · 15 s" inside a pair, "Rest · 60 s" otherwise (ADR-0065). */
export function restTitle(before: Guided['order'][number] | undefined, next: string): string {
  if (before === undefined) return 'Rest'
  return before.switch
    ? `Switch to ${next} · ${before.rest_seconds} s`
    : `Rest · ${before.rest_seconds} s`
}

/** Values kept on the server, as the screen holds them. */
export function fromKept(kept: Kept | null | undefined): Values {
  const values: Values = {}
  for (const d of kept?.sets ?? []) {
    const right = d.right ?? d.left
    const value: Value = { left: d.left, right, split: right !== d.left }
    if (d.started_at && d.done_at)
      Object.assign(value, { started_at: d.started_at, done_at: d.done_at })
    if (d.load_kg != null) value.load_kg = d.load_kg
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
    if (session.items[s.item].load && v.load_kg !== undefined) done.load_kg = v.load_kg
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

/** The weight a loaded set starts at (ADR-0072): what was confirmed; else the same set's
 * weight last time; with no history, the nearest set confirmed before it today, else the kit's
 * first weight. Undefined for a step without load. */
export function loadFor(session: Guided, values: Values, item: number, setNo: number) {
  const load = session.items[item].load
  if (!load) return undefined
  const confirmed = values[key(item, setNo)]?.load_kg
  if (confirmed !== undefined) return confirmed
  if (!load.carried)
    for (let n = setNo - 1; n >= 1; n--) {
      const before = values[key(item, n)]?.load_kg
      if (before !== undefined) return before
    }
  return load.kg[setNo - 1]
}

/** The items whose suggested weight the person took (ADR-0072): as they chose in this
 * screen, else any item with a set already confirmed at the suggested weight (a resume). */
export function taken(session: Guided, values: Values, chosen: Record<number, boolean>) {
  const found = new Set<number>()
  session.items.forEach((item, index) => {
    const up = item.load?.suggested
    if (!up) return
    const confirmed = item.targets.some((_, n) => values[key(index, n + 1)]?.load_kg === up.kg)
    if (chosen[index] ?? confirmed) found.add(index)
  })
  return found
}

/** The session as the screen shows it: an item whose suggested weight was taken starts every
 * set at that weight, with targets from the bottom of the range. Nothing changes until the
 * person taps; the server gets only what each set records. */
export function taking(session: Guided, items: Set<number>): Guided {
  if (items.size === 0) return session
  const shown = session.items.map((item, index) => {
    const up = item.load?.suggested
    if (!item.load || !up || !items.has(index)) return item
    return {
      ...item,
      targets: up.targets,
      load: { ...item.load, kg: item.load.kg.map(() => up.kg) },
    }
  })
  const order = session.order.map((s) =>
    items.has(s.item) && shown[s.item] !== session.items[s.item]
      ? { ...s, target: shown[s.item].targets[s.set_no - 1] }
      : s,
  )
  return { ...session, items: shown, order }
}

/** The session as the screen shows it, with the suggested weights the person took. */
export const shown = (session: Guided, values: Values, chosen: Record<number, boolean>) =>
  taking(session, taken(session, values, chosen))

/** Which items of ``session`` show a suggested weight taken in ``screen``. */
export const chosenIn = (session: Guided, screen: Guided): Record<number, boolean> =>
  Object.fromEntries(session.items.map((item, i) => [i, screen.items[i] !== item]))

/** ``values`` without ``item``'s sets not yet confirmed, so they start afresh at the weight
 * just taken or given back, and its targets. */
export function unweighed(values: Values, item: number): Values {
  return Object.fromEntries(
    Object.entries(values).filter(([at, value]) => !at.startsWith(`${item}:`) || value.done_at),
  )
}

/** "22.5 kg", as a person writes it. */
export const kgText = (kg: number) => `${kg}${NBSP}kg`
const NBSP = String.fromCharCode(0xa0) // the number and its unit stay on one line

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
    // One weight for every set reads once at the end; different weights go with each set.
    const kg = sets.flatMap((v) => (v?.load_kg === undefined ? [] : [v.load_kg]))
    const weights = new Set(kg)
    const shown =
      weights.size === 0
        ? done.join(' · ')
        : weights.size === 1
          ? `${done.join(' · ')} at ${kgText(kg[0])}`
          : sets
              .filter((v): v is Value => v !== null)
              .map((v, n) =>
                v.load_kg === undefined ? done[n] : `${done[n]} × ${kgText(v.load_kg)}`,
              )
              .join(' · ')
    const hit = sets.every(
      (v, n) => v !== null && v.left >= item.targets[n] && v.right >= item.targets[n],
    )
    return {
      name: item.name,
      target: item.targets.map((t) => unitText(item, t)).join(' · '),
      done: done.length ? shown : 'not done',
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
