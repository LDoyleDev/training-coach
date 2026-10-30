import { expect, test } from 'vitest'
import { BOX, BY_LOAD, BY_STEP, type Point, chart, fitSize, kindFor, split, strip } from './chart'

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

test('a session without a weight is its own period among weighed ones', () => {
  const points = [
    { day: '2026-10-01', best: 8, step_number: 1, kg: null },
    { day: '2026-10-05', best: 8, step_number: 1, kg: 20 },
  ]
  expect(kindFor(points)).toBe(BY_LOAD)
  expect(kindFor([points[0]])).toBe(BY_STEP)
  const found = chart(points, new Date(2026, 9, 21), BY_LOAD)!
  expect(found.periods.map((p) => p.key)).toEqual([0, 20])
  expect(BY_LOAD.name(0)).toBe('No weight')
  expect(BY_LOAD.words(20)).toBe('20 kg')
  expect(BY_LOAD.words(0)).toBe('no weight')
  expect(strip([])).toBeNull()
})

test('the kg strip breaks at a session without a weight, as the chart does', () => {
  const points = [
    { day: '2026-10-01', best: 8, step_number: 1, kg: 20 },
    { day: '2026-10-08', best: 8, step_number: 1, kg: null },
    { day: '2026-10-15', best: 8, step_number: 1, kg: 22.5 },
  ]
  const found = strip(chart(points, new Date(2026, 9, 21), BY_LOAD)!.dots)!
  expect(found.path.match(/M/g)).toHaveLength(2) // two runs, nothing drawn across the gap
  expect(found.path.split('M')[1]).not.toMatch(/V/) // 20 kg stays flat until its run ends
  expect([found.low, found.high]).toEqual([20, 22.5])
})

test('labels fit their room at the chart size or smaller; none keep the chart size', () => {
  expect(fitSize(['16 kg', '12 kg'], 30)).toBe(10)
  expect(fitSize(['102.5 kg', '97.5 kg'], 30)).toBe(6.8)
  expect(fitSize([], 30)).toBe(10)
})
