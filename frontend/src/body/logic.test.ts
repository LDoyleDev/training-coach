import { expect, test } from 'vitest'
import type { MeasureKind, Measurement } from '../api'
import { byDay, change, format, isoDay, latest, parse } from './logic'

const WEIGHT: MeasureKind = {
  kind: 'bodyweight',
  label: 'Bodyweight',
  unit: 'kg',
  decimals: 1,
  low: 30,
  high: 250,
}
const HEART: MeasureKind = {
  kind: 'resting_hr',
  label: 'Resting heart rate',
  unit: 'bpm',
  decimals: 0,
  low: 25,
  high: 150,
}

const m = (on: string, kind: Measurement['kind'], value: number): Measurement => ({
  on,
  kind,
  value,
})

test('values and changes to the kind’s precision', () => {
  expect(format(WEIGHT, 83)).toBe('83.0 kg')
  expect(format(HEART, 52)).toBe('52 bpm')
  expect(change(WEIGHT, 83.1, 84.3)).toBe('-1.2')
  expect(change(WEIGHT, 84.3, 83.1)).toBe('+1.2')
  expect(change(HEART, 52, 52)).toBe('±0')
})

test('the latest of each kind, against the first and the previous', () => {
  const entries = [
    m('2026-10-10', 'bodyweight', 83.1),
    m('2026-10-10', 'resting_hr', 52),
    m('2026-10-03', 'bodyweight', 83.6),
    m('2026-09-28', 'bodyweight', 84.2),
  ]
  expect(latest([WEIGHT, HEART], entries)).toEqual([
    { kind: WEIGHT, value: 83.1, on: '2026-10-10', first: 84.2, previous: 83.6 },
    { kind: HEART, value: 52, on: '2026-10-10', first: null, previous: null },
  ])
  // Two values: the older one is the first, with no separate previous.
  expect(latest([WEIGHT], entries.slice(0, 3))[0]).toMatchObject({ first: 83.6, previous: null })
  expect(latest([WEIGHT], [])).toEqual([])
})

test('entries by day, newest first', () => {
  const entries = [
    m('2026-10-10', 'bodyweight', 83),
    m('2026-10-10', 'waist', 85),
    m('2026-10-03', 'waist', 86),
  ]
  expect(byDay(entries).map(([on, list]) => [on, list.length])).toEqual([
    ['2026-10-10', 2],
    ['2026-10-03', 1],
  ])
})

test('typed values: blanks skipped, commas read as points, non-numbers named', () => {
  expect(parse([WEIGHT, HEART], { bodyweight: ' 83,4 ', resting_hr: '' })).toEqual({
    values: { bodyweight: 83.4 },
  })
  expect(parse([WEIGHT, HEART], { resting_hr: 'fast' })).toEqual({ invalid: 'Resting heart rate' })
})

test('a local day as YYYY-MM-DD', () => {
  expect(isoDay(new Date(2026, 9, 10))).toBe('2026-10-10')
  expect(isoDay(new Date(2026, 9, 10), 14)).toBe('2026-09-26')
})
