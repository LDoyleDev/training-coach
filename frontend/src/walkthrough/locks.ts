/**
 * The lock rule, a TS copy of `domain/locks.py` and `domain/kit.py`'s matching (ADR-0092,
 * Decided 19). During the walk a step that is locked for this person is never asked: one that
 * needs kit they haven't listed (ADR-0071) or asks something they've chosen to avoid (ADR-0083).
 * Worked out here from each step's needs and marks, so screen 8 needs no round trip; Save checks
 * every lock again on the server. Only whether a step is open is needed here: the walk never
 * shows a locked step, so the reasons in words stay on the server.
 */
import type { KitItem } from '../api'

export type Mark = 'floor' | 'kneeling' | 'impact' | 'hanging' | 'balance' | 'knees'

/** The marks a person can choose to avoid, in the order Account shows them. Balance has none. */
export const AVOIDABLE: Mark[] = ['floor', 'kneeling', 'impact', 'hanging', 'knees']

/** A band's strengths, weakest first. */
const STRENGTHS = ['light', 'medium', 'heavy']

/** What one step asks for: the catalogue's needs ("kettlebell:16", "pull-up bar") and marks. */
export interface Asks {
  needs: readonly string[]
  marks: readonly string[]
}

/** The person's home kit (null: not listed yet, so kit locks nothing) and what they avoid. */
export interface Limits {
  kit: readonly Pick<KitItem, 'kit' | 'kg' | 'min_kg' | 'resistance'>[] | null
  avoid: ReadonlySet<string>
}

type Owned = NonNullable<Limits['kit']>[number]

/** A need's kind and its weight (a band's: its strength's rank, 1 light to 3 heavy). */
function parse(need: string): [string, number | null] {
  const [kind, detail] = need.split(':', 2)
  if (detail === undefined) return [kind, null]
  if (kind === 'band') return [kind, STRENGTHS.indexOf(detail) + 1]
  return [kind, Number(detail)]
}

function meets(item: Owned, kind: string, kg: number | null): boolean {
  if (item.kit !== kind) return false
  if (kind === 'band' && kg !== null)
    return !!item.resistance && STRENGTHS.indexOf(item.resistance) + 1 >= kg
  if (kg === null || item.kg === null || item.kg === undefined) return kg === null
  if (kind === 'backpack') return item.kg >= kg
  if (item.min_kg !== null && item.min_kg !== undefined) return item.min_kg <= kg && kg <= item.kg
  return item.kg === kg
}

/** The needs a kit doesn't meet; none from a kit that isn't listed yet. */
export function missing(kit: Limits['kit'], needs: readonly string[]): string[] {
  if (kit === null) return []
  return needs.filter((need) => !kit.some((item) => meets(item, ...parse(need))))
}

/** The step's marks the person avoids, in Account's order. */
export function avoided(marks: readonly string[], avoid: ReadonlySet<string>): Mark[] {
  return AVOIDABLE.filter((m) => marks.includes(m) && avoid.has(m))
}

/** Whether nothing locks the step for this person. */
export function isOpen(asks: Asks, limits: Limits): boolean {
  return (
    missing(limits.kit, asks.needs).length === 0 && avoided(asks.marks, limits.avoid).length === 0
  )
}
