import { expect, test } from 'vitest'
import { after, type Draft, type Known, numberOf, ORDER, SAFETY } from './flow'

const NEW: Draft = { safety: {} }
const ALL: Known = { consent: true, residence: true, safety: true }
const NONE: Known = { consent: false, residence: false, safety: false }

/** Every screen from the welcome on, as `after` walks them. */
function walkAll(known: Known, draft: Draft): string[] {
  const seen = ['welcome']
  for (let at = after('welcome', known, draft); at; at = after(at, known, draft)) seen.push(at)
  return seen
}

test('with nothing on the server yet, every screen is asked in the ADR order', () => {
  expect(walkAll(ALL, NEW)).toEqual(ORDER.map((s) => s.id))
  expect(walkAll(ALL, NEW).slice(0, 4)).toEqual(['welcome', 'consent', 'residence', SAFETY[0]])
})

test('consent, where you live and current health answers are skipped', () => {
  expect(walkAll(NONE, NEW)).toEqual(['welcome', 'next'])
  expect(walkAll({ ...NONE, residence: true }, NEW)).toEqual(['welcome', 'residence', 'next'])
})

test('each screen carries its ADR number for the progress line', () => {
  expect(numberOf('welcome')).toBe(0)
  expect(numberOf('consent')).toBe(1)
  expect(numberOf(SAFETY[9])).toBe(3)
  expect(numberOf('safety-note')).toBe(3)
  expect(numberOf('nowhere')).toBe(0)
  expect(after('next', ALL, NEW)).toBeNull()
})
