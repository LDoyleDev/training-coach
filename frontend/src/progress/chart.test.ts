import { expect, test } from 'vitest'
import { BOX, type Point, chart, split } from './chart'

const today = new Date(2026, 9, 21) // the window runs 10 Sep to 21 Oct
const at = (day: string, best: number, step_number: number): Point => ({ day, best, step_number })
/** x of the window's day ``n`` (0 is 10 Sep, 41 is today). */
const x = (n: number) => BOX.left + (n / 41) * (BOX.width - BOX.left - BOX.right)

test('periods are runs of the same key, in order', () => {
  const key = (n: number) => n
  expect(split([1, 1, 2, 2, 2], key)).toEqual([
    [1, 1],
    [2, 2, 2],
  ]) // up
  expect(split([3, 3, 2], key)).toEqual([[3, 3], [2]]) // down, a one-item run
  expect(split([2, 2, 2], key)).toEqual([[2, 2, 2]]) // one period
  expect(split([1, 2, 1], key)).toEqual([[1], [2], [1]]) // back down: a new period
  expect(split([], key)).toEqual([])
})

test('one step is one period: a line through every session, no tint, no label', () => {
  const found = chart([at('2026-10-01', 8, 2), at('2026-10-08', 9, 2)], today)!
  expect(found.periods).toHaveLength(1)
  const [only] = found.periods
  expect(only).toMatchObject({ key: 2, move: null, label: null, tinted: false })
  expect([only.from, only.to]).toEqual([BOX.left, BOX.width - BOX.right])
  expect(only.line.split(' ')).toHaveLength(2)
})

test('a move up and a move down each start a period that the line does not cross', () => {
  const found = chart(
    [
      at('2026-10-01', 12, 1), // day 21
      at('2026-10-08', 7, 2), // day 28: up a step, fewer reps
      at('2026-10-15', 9, 2), // day 35
      at('2026-10-18', 11, 1), // day 38: back down
    ],
    today,
  )!
  const [first, up, down] = found.periods
  expect(found.periods.map((p) => [p.key, p.move, p.tinted])).toEqual([
    [1, null, false],
    [2, 'up', true],
    [1, 'down', false],
  ])
  // Each edge sits halfway between the sessions either side of the change.
  expect(up.from).toBeCloseTo(x(24.5))
  expect(first.to).toBe(up.from)
  expect(down.from).toBeCloseTo(x(36.5))
  expect(down.to).toBe(BOX.width - BOX.right)
  // One-session periods get a dot and no line; no line joins across a change.
  expect(first.line).toBe('')
  expect(up.line.split(' ')).toHaveLength(2)
  expect(down.line).toBe('')
  expect(up.label).toBe('Step 2 ↑')
  // The last period is too narrow for "Step 1 ↓" before the picture's edge, so it is short.
  expect(down.label).toBe('↓1')
})

test('a period too narrow for even the short label goes unlabelled', () => {
  const found = chart(
    [at('2026-10-10', 10, 1), at('2026-10-11', 8, 2), at('2026-10-12', 6, 3)],
    today,
  )!
  expect(found.periods.map((p) => p.move)).toEqual([null, 'up', 'up'])
  expect(found.periods.map((p) => p.label)).toEqual([null, null, 'Step 3 ↑'])
})
