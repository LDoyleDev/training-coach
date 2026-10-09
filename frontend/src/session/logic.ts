import type { Done, Guided, GuidedItem, Kept } from '../api'

/** One confirmed set as the screen holds it: `split` means left and right differ. */
export type Value = { left: number; right: number; split: boolean }
export type Values = Record<string, Value>

export const key = (item: number, setNo: number) => `${item}:${setNo}`

/** Values kept on the server, as the screen holds them. */
export function fromKept(kept: Kept | null | undefined): Values {
  const values: Values = {}
  for (const d of kept?.sets ?? []) {
    const right = d.right ?? d.left
    values[key(d.item, d.set_no)] = { left: d.left, right, split: right !== d.left }
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
    return [{ item: s.item, set_no: s.set_no, left: v.left, right: sided ? v.right : null }]
  })
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
