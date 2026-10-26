import type { BodyEstimate } from '../api'
import { local } from '../progress/chart'

/** One day's body fat, %: a scale reading or the tape estimate. */
export type FatPoint = Pick<BodyEstimate, 'on' | 'value'>

/** The plot area inside the viewBox; the gaps left and below hold the labels. */
export const FAT_BOX = { width: 300, height: 100, left: 30, right: 8, top: 8, bottom: 18 }

export interface FatDot {
  x: number
  y: number
  point: FatPoint
}

export interface FatSeries {
  dots: FatDot[] // oldest first
  line: string // the polyline through them; empty for a single point
}

export interface FatChart {
  scale: FatSeries
  tape: FatSeries
  low: number // whole per cent at the bottom of the one axis
  high: number // and at the top
  start: Date
  end: Date
}

/** Both lines on one % axis, dates along the bottom. Points are given newest first, as the
 * server lists them. Null when there is nothing to draw. */
export function fatChart(scale: FatPoint[], tape: FatPoint[]): FatChart | null {
  const all = [...scale, ...tape]
  if (all.length === 0) return null
  const times = all.map((p) => local(p.on).getTime())
  const first = Math.min(...times)
  const last = Math.max(...times)
  const values = all.map((p) => p.value)
  let low = Math.floor(Math.min(...values))
  let high = Math.ceil(Math.max(...values))
  if (high - low < 2) {
    // A flat run still gets a little room above and below, so it reads as flat, not as noise.
    const middle = Math.round((low + high) / 2)
    low = middle - 1
    high = middle + 1
  }
  const width = FAT_BOX.width - FAT_BOX.left - FAT_BOX.right
  const height = FAT_BOX.height - FAT_BOX.top - FAT_BOX.bottom
  const x = (on: string) =>
    last === first
      ? FAT_BOX.left + width / 2
      : FAT_BOX.left + ((local(on).getTime() - first) / (last - first)) * width
  const y = (v: number) => FAT_BOX.top + height - ((v - low) / (high - low)) * height
  const series = (points: FatPoint[]): FatSeries => {
    const dots = [...points]
      .reverse()
      .map((point) => ({ x: x(point.on), y: y(point.value), point }))
    const line =
      dots.length > 1 ? dots.map((d) => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' ') : ''
    return { dots, line }
  }
  return {
    scale: series(scale),
    tape: series(tape),
    low,
    high,
    start: new Date(first),
    end: new Date(last),
  }
}
