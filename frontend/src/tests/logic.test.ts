import { expect, test } from 'vitest'
import type { FitnessTest, TestDay } from '../api'
import { newToken, previous, sideText, stepOf, steps, timeOfDay, toSave, unitText } from './logic'

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
