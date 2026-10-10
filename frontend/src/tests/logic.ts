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

export type Compared = {
  test: string
  side: Side
  value: number
  baseline: number | null // the first test day with this result, when it isn't this one
  last: number | null // the test day before this one with it, when it isn't the baseline
}

/** Each result of `days[index]` next to the first baseline and the previous test (#96).
 * `days` is newest first, as the server lists them. */
export function compare(days: TestDay[], index: number): Compared[] {
  const earlier = days.slice(index + 1) // older days, newest first
  return days[index].results.map((r) => {
    const before = earlier.filter((d) =>
      d.results.some((o) => o.test === r.test && o.side === r.side),
    )
    const valueOn = (d: TestDay | undefined) =>
      d?.results.find((o) => o.test === r.test && o.side === r.side)?.value ?? null
    const first = before[before.length - 1]
    const last = before[0]
    return {
      test: r.test,
      side: r.side,
      value: r.value,
      baseline: valueOn(first),
      last: last === first ? null : valueOn(last),
    }
  })
}

export function change(now: number, then: number): string {
  const diff = now - then
  return diff === 0 ? '±0' : diff > 0 ? `+${diff}` : `${diff}`
}

/** What differs from the previous test day of the same day number: results compare only
 * under the same conditions (D4). Empty when they match or there's no earlier day. */
export function conditionsChanged(days: TestDay[], index: number): string[] {
  const now = days[index]
  const before = days.slice(index + 1).find((d) => d.day === now.day)
  if (!before) return []
  const changes: string[] = []
  if (before.time_of_day !== now.time_of_day)
    changes.push(`${now.time_of_day}, last time ${before.time_of_day}`)
  if (before.fed !== now.fed)
    changes.push(`${now.fed ? 'fed' : 'fasted'}, last time ${before.fed ? 'fed' : 'fasted'}`)
  if (before.slept_well !== now.slept_well)
    changes.push(
      `${now.slept_well ? 'slept well' : 'slept badly'}, last time ${before.slept_well ? 'slept well' : 'slept badly'}`,
    )
  return changes
}
