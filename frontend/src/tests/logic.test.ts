import { expect, test } from 'vitest'
import type { FitnessTest, TestDay } from '../api'
import {
  change,
  compare,
  conditionsChanged,
  newToken,
  previous,
  sideText,
  stepOf,
  steps,
  timeOfDay,
  toSave,
  unitText,
} from './logic'

const make = (over: Partial<FitnessTest>): FitnessTest => ({
  slug: 'x',
  name: 'X',
  day: 1,
  unit: 'reps',
  per_side: false,
  cue: 'c',
  low: 0,
  high: 500,
  ...over,
})

const PULL = make({ slug: 'pull', name: 'Pull-ups' })
const SPLIT = make({ slug: 'split', name: 'Split squat', day: 2, per_side: true })
const RUN = make({ slug: 'run', day: 2, unit: 'metres', high: 10000 })
const TOE = make({ slug: 'toe', day: 2, unit: 'cm', low: -60, high: 60 })

test('a day is one step per test, two for a one-sided test', () => {
  expect(steps([PULL, SPLIT, RUN], 2).map((s) => `${s.test.slug}:${s.side}`)).toEqual([
    'split:left',
    'split:right',
    'run:both',
  ])
  expect(steps([PULL, SPLIT], 1)).toHaveLength(1)
})

test('units, steps and sides', () => {
  expect(stepOf(PULL)).toBe(1)
  expect(stepOf(make({ unit: 'seconds' }))).toBe(5)
  expect(stepOf(RUN)).toBe(50)
  expect(unitText(make({ unit: 'seconds' }), 40)).toBe('40 s')
  expect(unitText(RUN, 2400)).toBe('2400 m')
  expect(unitText(TOE, 3)).toBe('+3 cm')
  expect(unitText(TOE, -4)).toBe('-4 cm')
  expect(unitText(PULL, 8)).toBe('8')
  expect([sideText('both'), sideText('left'), sideText('right')]).toEqual(['', 'Left', 'Right'])
})

test('the previous result is the newest day that has it', () => {
  const days = [
    { results: [{ test: 'run', side: 'both', value: 2500 }] },
    { results: [{ test: 'pull', side: 'both', value: 7 }] },
    { results: [{ test: 'pull', side: 'both', value: 5 }] },
  ] as TestDay[]
  expect(previous(days, 'pull', 'both')).toBe(7)
  expect(previous(days, 'split', 'left')).toBeNull()
})

test('a one-sided test is saved only with both sides', () => {
  const left = { test: 'split', side: 'left' as const, value: 12 }
  const right = { test: 'split', side: 'right' as const, value: 11 }
  const pull = { test: 'pull', side: 'both' as const, value: 8 }
  expect(toSave([PULL, SPLIT], [pull, left])).toEqual([pull])
  expect(toSave([PULL, SPLIT], [pull, left, right])).toEqual([pull, left, right])
})

test('time of day from the clock, and a token the server accepts', () => {
  expect([7, 12, 15, 20].map(timeOfDay)).toEqual(['morning', 'midday', 'afternoon', 'evening'])
  expect(newToken()).toMatch(/^[a-f0-9]{32}$/)
})

const day = (id: number, over: Partial<TestDay>, results: TestDay['results']): TestDay => ({
  id,
  on: `2026-10-0${id}`,
  day: 1,
  time_of_day: 'morning',
  fed: false,
  slept_well: true,
  results,
  ...over,
})

const pull = (value: number) => ({ test: 'pull', side: 'both' as const, value })

test('each result is set against the first baseline and the previous test', () => {
  const days = [
    day(3, {}, [pull(9), { test: 'hang', side: 'both', value: 40 }]),
    day(2, {}, [pull(8)]),
    day(1, {}, [pull(6)]),
  ]
  expect(compare(days, 0)).toEqual([
    { test: 'pull', side: 'both', value: 9, baseline: 6, last: 8, history: [9, 8, 6] },
    { test: 'hang', side: 'both', value: 40, baseline: null, last: null, history: [40] }, // first
  ])
  // With one earlier test, it is the baseline; there's no separate "last".
  expect(compare(days, 1)).toEqual([
    { test: 'pull', side: 'both', value: 8, baseline: 6, last: null, history: [8, 6] }, // not 9: later
  ])
  expect(compare(days, 2)[0]).toMatchObject({ baseline: null, last: null })
})

test('changes are signed', () => {
  expect([change(9, 6), change(6, 9), change(5, 5)]).toEqual(['+3', '-3', '±0'])
})

test('conditions that differ from the last test of the same day are named', () => {
  const days = [
    day(3, { time_of_day: 'evening', fed: true, slept_well: false }, []),
    day(2, { day: 2 }, []),
    day(1, {}, []),
  ]
  expect(conditionsChanged(days, 0)).toEqual([
    'evening, last time morning',
    'fed, last time fasted',
    'slept badly, last time slept well',
  ])
  expect(conditionsChanged(days, 1)).toEqual([]) // no earlier day 2
  expect(conditionsChanged([day(2, { fed: true }, []), day(1, { fed: false }, [])], 0)).toEqual([
    'fed, last time fasted',
  ])
  expect(
    conditionsChanged(
      [day(2, { fed: false, slept_well: false }, []), day(1, { fed: true, slept_well: true }, [])],
      0,
    ),
  ).toEqual(['fasted, last time fed', 'slept badly, last time slept well'])
  expect(
    conditionsChanged([day(2, { slept_well: true }, []), day(1, { slept_well: false }, [])], 0),
  ).toEqual(['slept well, last time slept badly'])
})
