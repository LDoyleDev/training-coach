import { expect, test } from 'vitest'
import shared from './day-cases.json?raw'
import { landing, startDay, starterDays, weekday } from './days'

// The cases backend/tests/domain/test_day_cases.py reads too, so the two copies can't drift.
interface Cases {
  starter_days: { tapped: number; days: number }[]
  landing: { case: string; start: string; rest_after: number[]; days: string[] }[]
  start_day: {
    case: string
    today: string
    weekdays: number[]
    rest_after: number[]
    on: string
    missed: number[]
  }[]
}
const cases = JSON.parse(shared) as Cases

/** "2026-11-09" as a local day at midnight, as days.ts works in. */
const local = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

test.each(cases.starter_days)('$tapped days tapped: the $days-day starter', ({ tapped, days }) => {
  expect(starterDays(tapped)).toBe(days)
})

test.each(cases.landing)('$case', ({ start, rest_after, days }) => {
  expect(landing(local(start), rest_after)).toEqual(days.map(local))
})

test.each(cases.start_day)('$case', ({ today, weekdays, rest_after, on, missed }) => {
  expect(startDay(local(today), weekdays, rest_after)).toEqual({ on: local(on), missed })
})

test('weekdays run from 0 Monday to 6 Sunday', () => {
  expect(weekday(local('2026-11-09'))).toBe(0)
  expect(weekday(local('2026-11-15'))).toBe(6)
})

test('the time of day is ignored', () => {
  expect(startDay(new Date(2026, 10, 9, 18, 30), [0], [2, 3]).on).toEqual(local('2026-11-09'))
})
