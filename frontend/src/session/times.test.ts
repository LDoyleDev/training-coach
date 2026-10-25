import { expect, test } from 'vitest'
import type { Guided } from '../api'
import { type Values } from './logic'
import { duration, soFar, times, wholeMinutes } from './times'

const item = (name: string, sets: number) => ({
  slug: name,
  name,
  step: '',
  summary: null,
  cue: null,
  unit: 'reps' as const,
  per_side: false,
  pair: 1,
  targets: Array(sets).fill(8),
  baseline: false,
  muscles: [],
  parts: [],
})

// A pair: A1, B1 (15 s switch), then A2 after a 60 s rest, then B2 after a 15 s switch.
const SESSION = {
  items: [item('A', 2), item('B', 2)],
  order: [
    { item: 0, set_no: 1, target: 8, rest_seconds: 15, switch: true },
    { item: 1, set_no: 1, target: 8, rest_seconds: 60, switch: false },
    { item: 0, set_no: 2, target: 8, rest_seconds: 15, switch: true },
    { item: 1, set_no: 2, target: 8, rest_seconds: 0, switch: false },
  ],
} as unknown as Guided

/** A set done from `from` to `to` seconds after 16:00. */
const set = (from: number, to: number) => ({
  left: 8,
  right: 8,
  split: false,
  started_at: new Date(Date.UTC(2026, 9, 20, 16, 0, from)).toISOString(),
  done_at: new Date(Date.UTC(2026, 9, 20, 16, 0, to)).toISOString(),
})

test('nothing timed is no times', () => {
  expect(times(SESSION, {})).toBeNull()
  expect(times(SESSION, { '0:1': { left: 8, right: 8, split: false } })).toBeNull()
  const bad = { ...set(0, 30), started_at: 'not a time' }
  expect(times(SESSION, { '0:1': bad })).toBeNull()
})

test('sets, rests and the time so far, on time', () => {
  const values: Values = {
    '0:1': set(0, 30),
    '1:1': set(45, 75), // 15 s switch, as planned
    '0:2': set(135, 165), // 60 s rest, as planned
    '1:2': set(180, 210),
  }
  const found = times(SESSION, values)
  expect(found).toMatchObject({ minutes: 4, onSets: 2, resting: 2, breaks: 0 })
  expect(found?.rows).toEqual([
    [
      { seconds: 30, slow: false, overran: null },
      { seconds: 30, slow: false, overran: null },
    ],
    [
      { seconds: 30, slow: false, overran: null },
      { seconds: 30, slow: false, overran: null },
    ],
  ])
})

test('a rest 30 s or more over its plan is marked on the set after it; 29 s is not', () => {
  const values: Values = {
    '0:1': set(0, 30),
    '1:1': set(74, 100), // 44 s against a 15 s switch: 29 over
    '0:2': set(190, 220), // 90 s against 60: 30 over
  }
  const rows = times(SESSION, values)?.rows
  expect(rows?.[1][0]?.overran).toBeNull()
  expect(rows?.[0][1]?.overran).toBe(30)
})

test('a much slower set is slow; a little slower is not', () => {
  const slow = times(SESSION, { '0:1': set(0, 34), '0:2': set(100, 160) })?.rows[0]
  expect(slow?.map((s) => s?.slow)).toEqual([false, true])
  const close = times(SESSION, { '0:1': set(0, 34), '0:2': set(100, 140) })?.rows[0]
  expect(close?.map((s) => s?.slow)).toEqual([false, false])
  // Short sets need 10 s more as well as half again: 8 s against 4 s is not slow.
  const short = times(SESSION, { '0:1': set(0, 4), '0:2': set(100, 108) })?.rows[0]
  expect(short?.map((s) => s?.slow)).toEqual([false, false])
  // One set has no other to compare with.
  expect(times(SESSION, { '0:1': set(0, 90) })?.rows[0]).toEqual([
    { seconds: 90, slow: false, overran: null },
  ])
})

test('a gap over 10 minutes is a break: out of the time and not an overrun', () => {
  const values: Values = { '0:1': set(0, 30), '1:1': set(30 + 601, 30 + 631) }
  const found = times(SESSION, values)
  expect(found).toMatchObject({ minutes: 1, onSets: 1, resting: 0, breaks: 1, onBreak: 10 })
  expect(found?.rows[1][0]?.overran).toBeNull()
  expect(soFar(found!)).toBe('So far 1 min: 1 on sets, 0 resting, plus 1 break (10 min).')
})

test('a set without times keeps its place with no time', () => {
  const values: Values = { '0:1': { left: 8, right: 8, split: false }, '0:2': set(100, 130) }
  expect(times(SESSION, values)?.rows[0]).toEqual([
    null,
    { seconds: 30, slow: false, overran: null },
  ])
})

test('overlapping sets rest nothing', () => {
  const found = times(SESSION, { '0:1': set(0, 60), '1:1': set(30, 90) })
  expect(found?.resting).toBe(0)
})

test.each([
  [0, 0],
  [10, 1],
  [89, 1],
  [91, 2],
])('%i s is %i whole minutes', (seconds, minutes) => {
  expect(wholeMinutes(seconds)).toBe(minutes)
})

test('durations read as seconds, then minutes from two', () => {
  expect(duration(34)).toBe('34s')
  expect(duration(119)).toBe('119s')
  expect(duration(600)).toBe('10 min')
})

test('the time so far, with breaks counted apart', () => {
  const base = { minutes: 23, onSets: 9, resting: 14, rows: [] }
  expect(soFar({ ...base, breaks: 0, onBreak: 0 })).toBe('So far 23 min: 9 on sets, 14 resting.')
  expect(soFar({ ...base, breaks: 2, onBreak: 30 })).toBe(
    'So far 23 min: 9 on sets, 14 resting, plus 2 breaks (30 min).',
  )
})
