import type { MeasureKind, Measurement } from '../api'

export function format(kind: MeasureKind, value: number): string {
  return `${value.toFixed(kind.decimals)} ${kind.unit}`
}

/** A signed change, to the kind's precision: "+1.2", "-0.4", "±0". */
export function change(kind: MeasureKind, now: number, then: number): string {
  const diff = Number((now - then).toFixed(kind.decimals))
  if (diff === 0) return '±0'
  return `${diff > 0 ? '+' : ''}${diff.toFixed(kind.decimals)}`
}

export type Latest = {
  kind: MeasureKind
  value: number
  on: string
  first: number | null // the first ever, when it isn't the latest
  previous: number | null // the one before the latest, when it isn't the first
}

/** Each kind's latest value with the first and previous to compare. `entries` are newest
 * first, as the server lists them. Kinds never measured are left out. */
export function latest(kinds: MeasureKind[], entries: Measurement[]): Latest[] {
  return kinds.flatMap((kind): Latest[] => {
    const mine = entries.filter((e) => e.kind === kind.kind)
    if (mine.length === 0) return []
    const first = mine.length > 1 ? mine[mine.length - 1].value : null
    const previous = mine.length > 2 ? mine[1].value : null
    return [{ kind, value: mine[0].value, on: mine[0].on, first, previous }]
  })
}

/** Entries grouped by day, newest first, keeping the server's order within a day. */
export function byDay(entries: Measurement[]): [string, Measurement[]][] {
  const days = new Map<string, Measurement[]>()
  for (const entry of entries) days.set(entry.on, [...(days.get(entry.on) ?? []), entry])
  return [...days.entries()]
}

/** The typed values to save: numbers for the filled-in fields, or a field that isn't one. */
export function parse(
  kinds: MeasureKind[],
  typed: Record<string, string>,
): { values: Record<string, number> } | { invalid: string } {
  const values: Record<string, number> = {}
  for (const kind of kinds) {
    const text = (typed[kind.kind] ?? '').trim().replace(',', '.')
    if (text === '') continue
    const value = Number(text)
    if (!Number.isFinite(value)) return { invalid: kind.label }
    values[kind.kind] = value
  }
  return { values }
}

/** YYYY-MM-DD for a local date, `days` before `from`. */
export function isoDay(from: Date, days = 0): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate() - days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
