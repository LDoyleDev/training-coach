import { expect, test } from 'vitest'
import { landing, startDay, starterDays, weekday } from './days'

// The same cases as backend/tests/domain/test_walkthrough.py.
const MONDAY = new Date(2026, 10, 9)
const on = (date: number) => new Date(2026, 10, date)
const [TWO, THREE, FOUR] = [
  [2, 3],
  [1, 1, 2],
  [0, 1, 0, 2],
] // the starters' rest places (plan.toml)

test.each([
  [0, 3],
  [1, 2],
  [2, 2],
  [3, 3],
  [4, 4],
  [5, 4],
  [7, 4],
])('%i days tapped: the %i-day starter', (tapped, days) => {
  expect(starterDays(tapped)).toBe(days)
})

test('each session lands after the rest places before it', () => {
  expect(landing(MONDAY, THREE)).toEqual([MONDAY, on(11), on(13)])
  expect(weekday(MONDAY)).toBe(0)
  expect(weekday(on(15))).toBe(6) // Sunday
})

test('Monday, Wednesday, Friday starts today on the 3-day and misses nothing', () => {
  expect(startDay(MONDAY, [0, 2, 4], THREE)).toEqual({ on: MONDAY, missed: [] })
})

test('the start is the tapped day that lands the most sessions, not the first', () => {
  // Tue, Thu, Sat tapped on a Monday: from Tuesday A Tue, B Thu, C Sat.
  expect(startDay(MONDAY, [5, 1, 3], THREE)).toEqual({ on: on(10), missed: [] })
})

test("days that don't fit the pattern are named", () => {
  // Mon and Tue on the 2-day: one is always missed, so the first, today, wins.
  expect(startDay(MONDAY, [0, 1], TWO)).toEqual({ on: MONDAY, missed: [1] })
})

test('a tapped day later in the week starts then', () => {
  // Thu: L1 Thu, U1 Fri, L2 Sun, U2 Mon.
  expect(startDay(MONDAY, [3, 4, 5, 6], FOUR)).toEqual({ on: on(12), missed: [5] })
})

test('nothing tapped starts tomorrow, and the time of day is ignored', () => {
  expect(startDay(MONDAY, [], THREE)).toEqual({ on: on(10), missed: [] })
  expect(startDay(new Date(2026, 10, 9, 18, 30), [0], TWO).on).toEqual(MONDAY)
})
