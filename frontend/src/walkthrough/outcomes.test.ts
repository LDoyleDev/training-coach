import { expect, test } from 'vitest'
import type { Draft, Known } from './flow'
import { type About, NOTHING_ANSWERED } from './level'
import { easyStartOf } from './outcomes'

const KNOWN: Known = { consent: false, residence: false, safety: false, ladders: [] }
const DRAFT: Draft = {
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
  placement: {},
  days: [],
  minutes: null,
  count: null,
  chosen: {},
  putBack: false,
  easyStart: null,
}
// Every answer at the top: a suggested level of 4.
const FIT: About = {
  age: '35-49',
  often: 'three_plus',
  effort: 'breathless',
  howLong: 'over_30',
  chair: true,
  stairs: true,
  walk: true,
  floor: true,
}
const of = (about: Partial<About>, easyStart: boolean | null = null) =>
  easyStartOf(KNOWN, { ...DRAFT, about: { ...FIT, ...about }, easyStart })

test.each([
  ['level 1', { chair: false }, true],
  ['level 2', { often: 'under_weekly' }, true],
  ['level 3', { often: 'one_two' }, true],
  ['level 3 at 65 and over', { age: '65-74' }, true],
  ['level 4', {}, false],
] as const)('the easy start at %s', (_, about, on) => {
  expect(of(about)).toEqual({ on, suggested: on })
})

test('suggested when more than half of screens 4-6 were skipped, not at half', () => {
  const skipped = { chair: null, stairs: null, walk: null, floor: null } // 4 of 8
  expect(of(skipped).suggested).toBe(false)
  expect(of({ ...skipped, age: null }).suggested).toBe(true) // 5 of 8
  expect(easyStartOf(KNOWN, DRAFT)).toEqual({ on: true, suggested: true }) // nothing answered
})

test('as tapped, whatever is suggested', () => {
  expect(of({}, true)).toEqual({ on: true, suggested: false })
  expect(of({ chair: false }, false)).toEqual({ on: false, suggested: true })
})
