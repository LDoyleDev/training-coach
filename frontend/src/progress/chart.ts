import type { Standing } from '../api'

/** The Progress graphs' window, as TREND_WEEKS on the server. */
export const WEEKS = 6
const DAYS = WEEKS * 7

export type Point = Standing['trend'][number]

/** The plot area inside the graph's viewBox; the gaps left and below hold the labels. */
export const BOX = { width: 300, height: 96, left: 34, right: 8, top: 14, bottom: 18 }

/** A label's width per character in viewBox units at the chart's 10-unit text: Archivo's
 * figures and capitals run about 5.5 to 6, small letters and spaces less, so this is generous. */
const CHAR = 5.5
/** The gap between a period's edge and its label, and between a label and the next edge. */
export const PAD = 3

/** The text size, the chart's 10 or smaller, at which every one of ``labels`` fits ``room``
 * viewBox units: a weight such as "102.5 kg" is wider than the gap left of the plot, and would
 * otherwise run off the picture's edge. One size for all, so the labels look alike. */
export function fitSize(labels: string[], room: number): number {
  const longest = Math.max(0, ...labels.map((label) => label.length))
  if (longest === 0) return 10 // nothing to fit
  return Math.min(10, Math.floor((room / (longest * CHAR)) * 100) / 10)
}

export interface Dot {
  x: number
  y: number
  point: Point
}

/** What makes a period (ADR-0072): consecutive sessions with the same key are one period, and
 * the chart names a change by its key. Ladder steps today; a load in kg later, the same way. */
export interface PeriodKind {
  key: (point: Point) => number
  name: (key: number) => string // on the chart, before the arrow: "Step 3"
  words: (key: number) => string // in the description: "step 3"
}

export const BY_STEP: PeriodKind = {
  key: (p) => p.step_number,
  name: (k) => `Step ${k}`,
  words: (k) => `step ${k}`,
}

/** Periods by the session's weight, on a loaded step (ADR-0072); a session without one is 0. */
export const BY_LOAD: PeriodKind = {
  key: (p) => p.kg ?? 0,
  name: (k) => (k === 0 ? 'No weight' : `${k} kg`),
  words: (k) => (k === 0 ? 'no weight' : `${k} kg`),
}

/** By weight when any session in the window has one, else by ladder step. */
export const kindFor = (points: Point[]): PeriodKind =>
  points.some((p) => p.kg != null) ? BY_LOAD : BY_STEP

/** The thin strip under a loaded exercise's chart (ADR-0072): its weight per session as a
 * staircase on the same dates, never a second scale on the chart itself. */
export const STRIP = { height: 30, top: 6, bottom: 6 }

export interface Strip {
  path: string // a staircase through each weighed session
  low: number
  high: number
}

export function strip(dots: Dot[]): Strip | null {
  const kg = dots.flatMap((d) => (d.point.kg != null ? [d.point.kg] : []))
  if (kg.length === 0) return null
  const low = Math.min(...kg)
  const high = Math.max(...kg)
  const room = STRIP.height - STRIP.top - STRIP.bottom
  const y = (v: number) =>
    high === low ? STRIP.top + room / 2 : STRIP.top + room - ((v - low) / (high - low)) * room
  // A staircase through each run of weighed sessions; a session without a weight breaks it,
  // as the chart starts a "No weight" period there.
  let path = ''
  let drawing = false
  for (const d of dots) {
    const x = d.x.toFixed(1)
    if (d.point.kg == null) {
      drawing = false
      continue
    }
    const at = y(d.point.kg).toFixed(1)
    path += drawing ? `H${x}V${at}` : `M${x},${at}`
    drawing = true
  }
  if (drawing) path += `H${Math.max(dots.at(-1)!.x, BOX.width - BOX.right).toFixed(1)}`
  return { path, low, high }
}

export interface Period {
  key: number
  dots: Dot[]
  line: string // the polyline through its sessions; empty for a one-session period
  from: number // x of its left edge
  to: number // x of its right edge
  tinted: boolean // every other period, from the second, has a faint background
  move: 'up' | 'down' | null // against the period before; null for the first
  label: string | null // what fits at its top-left: "Step 3 ↑", "↑3", or nothing
}

export interface Chart {
  dots: Dot[]
  periods: Period[]
  weeks: number[] // x of each week's gridline
  low: number
  high: number
  start: Date // the window's first day
}

/** Runs of consecutive items with the same key, in order. */
export function split<T>(items: readonly T[], key: (item: T) => number): T[][] {
  const runs: T[][] = []
  for (const item of items) {
    const last = runs.at(-1)
    if (last && key(last[0]) === key(item)) last.push(item)
    else runs.push([item])
  }
  return runs
}

/** A date from the server ("2026-10-21") as local midnight. */
export function local(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function midnight(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate())
}

const fits = (text: string, room: number) => text.length * CHAR <= room

/** Where each session sits on a graph of the last six weeks to ``today``: dates along the
 * bottom, the best set up the side (lowest to highest seen), split into periods by ``kind``. */
export function chart(points: Point[], today: Date, kind: PeriodKind = BY_STEP): Chart | null {
  if (points.length === 0) return null
  const end = midnight(today)
  const start = new Date(end.getFullYear(), end.getMonth(), end.getDate() - (DAYS - 1))
  const width = BOX.width - BOX.left - BOX.right
  const height = BOX.height - BOX.top - BOX.bottom
  const at = (day: Date) => {
    const index = Math.round((day.getTime() - start.getTime()) / 86_400_000)
    return BOX.left + (Math.min(Math.max(index, 0), DAYS - 1) / (DAYS - 1)) * width
  }
  const values = points.map((p) => p.best)
  const low = Math.min(...values)
  const high = Math.max(...values)
  const y = (v: number) =>
    high === low ? BOX.top + height / 2 : BOX.top + height - ((v - low) / (high - low)) * height
  const dots = points.map((point) => ({ x: at(local(point.day)), y: y(point.best), point }))
  const runs = split(dots, (d) => kind.key(d.point))
  // A period starts halfway between the last session before it and its own first one.
  const edges = runs.map((run, i) => (i === 0 ? BOX.left : (runs[i - 1].at(-1)!.x + run[0].x) / 2))
  const periods = runs.map((run, i): Period => {
    const key = kind.key(run[0].point)
    const before = i === 0 ? null : kind.key(runs[i - 1][0].point)
    const move = before === null ? null : key > before ? 'up' : 'down'
    const from = edges[i]
    const to = i + 1 < runs.length ? edges[i + 1] : BOX.width - BOX.right
    // The label may run to the next period's label, or to the edge of the picture.
    const room = (i + 1 < runs.length ? edges[i + 1] : BOX.width) - from - 2 * PAD
    const arrow = move === 'up' ? '↑' : '↓'
    const full = `${kind.name(key)} ${arrow}`
    const short = `${arrow}${key}`
    return {
      key,
      dots: run,
      line: run.length > 1 ? run.map((d) => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' ') : '',
      from,
      to,
      tinted: i % 2 === 1,
      move,
      label: move === null ? null : fits(full, room) ? full : fits(short, room) ? short : null,
    }
  })
  const weeks = Array.from({ length: WEEKS + 1 }, (_, w) =>
    at(new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7)),
  )
  return { dots, periods, weeks, low, high, start }
}

export function shortDay(day: Date): string {
  return day.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
