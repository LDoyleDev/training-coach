import type { KitItem, KitItemBody, KitKind } from '../api'

/** Where "My equipment" lives, for links from a locked step (ADR-0071). */
export const KIT_HREF = '/account#my-equipment'

export type Resistance = NonNullable<KitItemBody['resistance']>
export const RESISTANCES: Resistance[] = ['light', 'medium', 'heavy']

/** Kit that comes with a weight in kg; the rest is there or not. */
const WEIGHED: KitKind[] = ['kettlebell', 'dumbbells', 'backpack']

/** The item being added or edited, as typed. */
export type Draft = {
  kit: KitKind
  kg: string
  minKg: string // adjustable dumbbells: the bottom of the range, kg the top
  adjustable: boolean
  resistance: Resistance | null
  note: string
}

export function blank(kit: KitKind): Draft {
  return { kit, kg: '', minKg: '', adjustable: false, resistance: null, note: '' }
}

export function draftOf(item: KitItem): Draft {
  return {
    kit: item.kit,
    kg: item.kg?.toString() ?? '',
    minKg: item.min_kg?.toString() ?? '',
    adjustable: item.min_kg !== null && item.min_kg !== undefined,
    resistance: item.resistance ?? null,
    note: item.note,
  }
}

const kg = (text: string): number | null => {
  const value = Number(text.trim().replace(',', '.'))
  return text.trim() && Number.isFinite(value) ? value : null
}

/** The draft as the API takes it, or null while something it needs is still empty. The server
 * checks the rest (range, steps of 0.5 kg) and says why. */
export function bodyOf(draft: Draft): KitItemBody | null {
  const note = draft.note.trim()
  if (draft.kit === 'band')
    return draft.resistance ? { kit: 'band', resistance: draft.resistance, note } : null
  if (!WEIGHED.includes(draft.kit)) return { kit: draft.kit, note }
  const top = kg(draft.kg)
  if (top === null) return null
  if (draft.kit === 'dumbbells' && draft.adjustable) {
    const bottom = kg(draft.minKg)
    return bottom === null ? null : { kit: 'dumbbells', kg: top, min_kg: bottom, note }
  }
  return { kit: draft.kit, kg: top, note }
}

/** A saved item as the API takes it back, for a PUT of the whole list. */
export function bodyFromItem(item: KitItem): KitItemBody {
  return {
    kit: item.kit,
    kg: item.kg ?? null,
    min_kg: item.min_kg ?? null,
    resistance: item.resistance ?? null,
    note: item.note,
  }
}

/** The short form the unlocks question takes: `kettlebell:16`, `dumbbells:2-24`, `band:light`,
 * `pull-up bar`. */
export function token(body: KitItemBody): string {
  if (body.kit === 'band') return `band:${body.resistance}`
  if (body.min_kg !== null && body.min_kg !== undefined)
    return `dumbbells:${body.min_kg}-${body.kg}`
  if (body.kg !== null && body.kg !== undefined) return `${body.kit}:${body.kg}`
  return body.kit
}

export const STABLE = 'Check it’s stable before loading it.'

/** A short hint for each kind, shown while adding it. */
export const HINTS: Partial<Record<KitKind, string>> = {
  bench: `Something stable to lie on: a flat bench, stools or a bed. ${STABLE}`,
  backpack: 'A weighted vest, or a backpack you can load: say the most it holds.',
  dumbbells: 'A fixed pair of one weight, or an adjustable set with its range.',
  kettlebell: 'Each weight is its own item: add a 16 kg and a 24 kg separately.',
}

/** What the note could say, per kind. */
export function placeholder(kit: KitKind): string {
  if (kit === 'bench') return 'two stools'
  if (kit === 'dip bars') return 'two kitchen chairs'
  if (kit === 'box') return 'the bottom stair'
  return 'optional'
}
