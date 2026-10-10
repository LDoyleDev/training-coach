import type { Standing } from '../api'

export function amount(standing: Standing, value: number): string {
  if (standing.unit === 'seconds') return `${value} s`
  if (standing.unit === 'minutes') return `${value} min`
  return `${value}`
}

/** Points for a small line of the best set per session, oldest on the left. */
export function trend(recent: number[], width = 120, height = 32): string {
  const values = [...recent].reverse()
  if (values.length < 2) return ''
  const low = Math.min(...values)
  const high = Math.max(...values)
  const span = high - low || 1
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width
      const y = height - ((v - low) / span) * (height - 4) - 2
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}
