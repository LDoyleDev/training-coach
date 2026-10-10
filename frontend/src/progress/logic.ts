import type { Standing } from '../api'

export function amount(standing: Standing, value: number): string {
  if (standing.unit === 'seconds') return `${value} s`
  if (standing.unit === 'minutes') return `${value} min`
  return `${value}`
}

export { trend } from '../components/trend'
