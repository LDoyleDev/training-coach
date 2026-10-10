import type { FitnessTest, TestDay, TestResult } from '../api'

export type Side = 'both' | 'left' | 'right'

/** One entry screen: a test, or one side of a one-sided test. */
export type Step = { test: FitnessTest; side: Side }

export function steps(tests: FitnessTest[], day: number): Step[] {
  return tests
    .filter((t) => t.day === day)
    .flatMap((test): Step[] =>
      test.per_side
        ? [
            { test, side: 'left' },
            { test, side: 'right' },
          ]
        : [{ test, side: 'both' }],
    )
}

/** How much one tap of + or − changes a result. */
export function stepOf(test: FitnessTest): number {
  if (test.unit === 'seconds') return 5
  if (test.unit === 'metres') return 50
  return 1
}

export function unitText(test: FitnessTest, value: number): string {
  if (test.unit === 'seconds') return `${value} s`
  if (test.unit === 'metres') return `${value} m`
  if (test.unit === 'cm') return `${value > 0 ? '+' : ''}${value} cm`
  return `${value}`
}

export function sideText(side: Side): string {
  return side === 'both' ? '' : side === 'left' ? 'Left' : 'Right'
}

/** The latest saved result for a test and side, to start from and compare with. */
export function previous(days: TestDay[], test: string, side: Side): number | null {
  for (const day of days) {
    const found = day.results.find((r) => r.test === test && r.side === side)
    if (found) return found.value
  }
  return null
}

/** Results to save: a one-sided test only when both sides were done (skip one, skip both). */
export function toSave(tests: FitnessTest[], results: TestResult[]): TestResult[] {
  return results.filter((r) => {
    const test = tests.find((t) => t.slug === r.test)
    if (!test?.per_side) return true
    return results.some((o) => o.test === r.test && o.side !== r.side)
  })
}

/** A guess at the time of day from the clock, for the conditions screen. */
export function timeOfDay(hour: number): 'morning' | 'midday' | 'afternoon' | 'evening' {
  if (hour < 11) return 'morning'
  if (hour < 14) return 'midday'
  if (hour < 18) return 'afternoon'
  return 'evening'
}

export function newToken(): string {
  return crypto.randomUUID().replaceAll('-', '')
}
