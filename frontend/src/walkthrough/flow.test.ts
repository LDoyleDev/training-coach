import { expect, test } from 'vitest'
import { after, type Draft, type Known, numberOf, ORDER, SAFETY } from './flow'
import { NOTHING_ANSWERED } from './level'

const NEW: Draft = {
  about: NOTHING_ANSWERED,
  safety: {},
  avoid: {
    avoid_floor: false,
    avoid_kneeling: false,
    avoid_impact: false,
    avoid_hanging: false,
    avoid_knees: false,
  },
  places: 'home',
  kit: null,
}
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
  expect(walkAll(NONE, NEW).slice(0, 3)).toEqual(['welcome', 'age', 'often'])
  expect(walkAll({ ...NONE, residence: true }, NEW).slice(0, 2)).toEqual(['welcome', 'residence'])
})

test('how hard and how long are only asked of someone who exercises now', () => {
  const resting = { ...NEW, about: { ...NEW.about, often: 'not_now' as const } }
  expect(after('often', NONE, resting)).toBe('chair')
  expect(after('often', NONE, NEW)).toBe('effort') // skipped counts as asking on
})

test('the home kit is skipped for the gym only', () => {
  expect(after('places', NONE, { ...NEW, places: 'gym' })).toBe('next')
  expect(after('places', NONE, { ...NEW, places: 'both' })).toBe('kit')
})

test('each screen carries its ADR number for the progress line', () => {
  expect(numberOf('welcome')).toBe(0)
  expect(numberOf(SAFETY[9])).toBe(3)
  expect(numberOf('howLong')).toBe(5)
  expect(numberOf('floor')).toBe(6)
  expect(numberOf('kit')).toBe(8)
  expect(numberOf('nowhere')).toBe(0)
  expect(after('next', ALL, NEW)).toBeNull()
})
