import type { Standing } from '../api'

/** The Progress graphs' window, as TREND_WEEKS on the server. */
export const WEEKS = 6
const DAYS = WEEKS * 7

export type Point = Standing['trend'][number]

/** The plot area inside the graph's viewBox; the gaps left and below hold the labels. */
export const BOX = { width: 300, height: 96, left: 34, right: 8, top: 14, bottom: 18 }

export interface Chart {
  dots: { x: number; y: number; point: Point }[]
  line: string
  moves: { x: number; step: number }[] // where a session is on a higher step than the one before
  weeks: number[] // x of each week's gridline
  low: number
  high: number
  start: Date // the window's first day
}

function local(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function midnight(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate())
}

/** Where each session sits on a graph of the last six weeks to ``today``: dates along the
 * bottom, the best set up the side (lowest to highest seen), and a mark at each move up. */
export function chart(points: Point[], today: Date): Chart | null {
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
  const moves = dots
    .filter((d, i) => i > 0 && d.point.step_number > points[i - 1].step_number)
    .map((d) => ({ x: d.x, step: d.point.step_number }))
  const weeks = Array.from({ length: WEEKS + 1 }, (_, w) =>
    at(new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7)),
  )
  return {
    dots,
    line: dots.map((d) => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' '),
    moves,
    weeks,
    low,
    high,
    start,
  }
}

export function shortDay(day: Date): string {
  return day.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
