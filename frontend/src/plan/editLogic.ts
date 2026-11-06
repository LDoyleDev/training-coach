import type { CatalogueItem, EditItem, EditSession, ItemChange, Place } from '../api'

/** A draft of the plan: each session's versions by place, as edited so far. Nothing is saved until
 * Save (program-builder.md F). */
export type Draft = Record<string, Record<Place, EditItem[]>>

export const PLACES: { place: Place; label: string }[] = [
  { place: 'home', label: 'Home' },
  { place: 'gym', label: 'Gym' },
  { place: 'away', label: 'Away' },
]

export function draftOf(sessions: EditSession[]): Draft {
  return Object.fromEntries(
    sessions.map((s) => [s.slug, { home: s.home, gym: s.gym, away: s.away }]),
  )
}

const same = (a: EditItem, b: EditItem) =>
  a.exercise === b.exercise &&
  a.sets === b.sets &&
  a.rep_min === b.rep_min &&
  a.rep_max === b.rep_max &&
  a.per_side === b.per_side &&
  a.pair === b.pair

/** The versions that differ from what was loaded: only these are sent. */
export function changed(
  draft: Draft,
  sessions: EditSession[],
): { slug: string; place: Place; items: ItemChange[] }[] {
  const out: { slug: string; place: Place; items: ItemChange[] }[] = []
  for (const session of sessions) {
    for (const { place } of PLACES) {
      const now = draft[session.slug]![place]
      const was = session[place]
      if (now.length === was.length && now.every((item, i) => same(item, was[i]!))) continue
      out.push({
        slug: session.slug,
        place,
        items: now.map(({ exercise, sets, rep_min, rep_max, per_side, pair }) => ({
          exercise,
          sets,
          rep_min,
          rep_max,
          per_side,
          pair,
        })),
      })
    }
  }
  return out
}

/** The list with this item changed. A pair stays only while its two are still neighbours. */
export function withItem(items: EditItem[], at: number, change: Partial<EditItem>): EditItem[] {
  return items.map((item, i) => (i === at ? { ...item, ...change } : item))
}

/** A pair number marks two neighbours (ADR-0031): any other number left behind is cleared. */
function tidyPairs(items: EditItem[]): EditItem[] {
  return items.map((item, i) => {
    if (item.pair === null) return item
    const beside = items[i - 1]?.pair === item.pair || items[i + 1]?.pair === item.pair
    return beside ? item : { ...item, pair: null }
  })
}

export function moved(items: EditItem[], at: number, by: -1 | 1): EditItem[] {
  const to = at + by
  if (to < 0 || to >= items.length) return items
  const next = [...items]
  const [item] = next.splice(at, 1)
  next.splice(to, 0, { ...item!, pair: null })
  return tidyPairs(next.map((other, i) => (i === at ? { ...other, pair: null } : other)))
}

export function removed(items: EditItem[], at: number): EditItem[] {
  return tidyPairs(items.filter((_, i) => i !== at))
}

/** Whether this item and the next are done alternately, set by set. */
export const paired = (items: EditItem[], at: number) => {
  const pair = items[at]?.pair ?? null
  return pair !== null && items[at + 1]?.pair === pair
}

/** Pair this item with the next, or part them. */
export function togglePair(items: EditItem[], at: number): EditItem[] {
  if (at + 1 >= items.length) return items
  if (paired(items, at)) {
    return items.map((item, i) => (i === at || i === at + 1 ? { ...item, pair: null } : item))
  }
  const number = Math.max(0, ...items.map((item) => item.pair ?? 0)) + 1
  return tidyPairs(
    items.map((item, i) => (i === at || i === at + 1 ? { ...item, pair: number } : item)),
  )
}

const DEFAULT_RANGE: [number, number] = [8, 12]

/** A catalogue exercise as a new item: its own range if it has one, 3 sets to start. */
export function newItem(from: CatalogueItem): EditItem {
  const [rep_min, rep_max] = from.range ?? DEFAULT_RANGE
  return {
    exercise: from.slug,
    name: from.name,
    sets: 3,
    rep_min,
    rep_max,
    per_side: from.per_side,
    pair: null,
  }
}

/** The new exercise in this one's place, keeping its sets and range. */
export function swapped(items: EditItem[], at: number, from: CatalogueItem): EditItem[] {
  return tidyPairs(
    withItem(items, at, {
      exercise: from.slug,
      name: from.name,
      per_side: from.per_side,
      pair: items[at]!.pair,
    }),
  )
}

/** What can be picked at this place, optionally training this muscle, biggest share first. */
export function choices(
  catalogue: CatalogueItem[],
  place: Place,
  muscle: string | null,
): CatalogueItem[] {
  const open = catalogue.filter((e) => e.places.includes(place))
  if (!muscle) return [...open].sort((a, b) => a.name.localeCompare(b.name))
  return open
    .filter((e) => (e.muscles[muscle] ?? 0) > 0)
    .sort(
      (a, b) => (b.muscles[muscle] ?? 0) - (a.muscles[muscle] ?? 0) || a.name.localeCompare(b.name),
    )
}

export function muscles(catalogue: CatalogueItem[]): string[] {
  return [...new Set(catalogue.flatMap((e) => Object.keys(e.muscles)))].sort()
}
