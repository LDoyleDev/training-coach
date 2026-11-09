import { expect, test } from 'vitest'
import type { WalkLadder } from './api'
import { after, type Draft, type Known, ladderAt, numberOf, ORDER, rungsOf, SAFETY } from './flow'
import { NOTHING_ANSWERED } from './level'

const step = (
  id: number,
  level: number | null,
  more: { needs?: string[]; marks?: string[] } = {},
) => ({
  id,
  position: id % 10,
  name: `Step ${id}`,
  level,
  question: id % 10 === 0 ? null : `Can you do 10 of step ${id}?`, // the bottom has none
  cue: null,
  needs: [],
  marks: [],
  ...more,
})
// Levels 1 to 5; the fourth step asks for the floor.
const PUSH: WalkLadder = {
  slug: 'push-up',
  name: 'Push-up',
  on: null,
  steps: [step(10, 1), step(11, 2), step(12, 3), step(13, 4, { marks: ['floor'] }), step(14, 5)],
}
// A bottom step, then a 16 kg kettlebell.
const SWING: WalkLadder = {
  slug: 'swing',
  name: 'Swing',
  on: null,
  steps: [step(20, 2), step(21, 4, { needs: ['kettlebell:16'] })],
}
const LADDERS = [PUSH, SWING]

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
  placement: {},
  days: [],
  minutes: null,
  count: null,
}
const ALL: Known = { consent: true, residence: true, safety: true, ladders: LADDERS }
const NONE: Known = { consent: false, residence: false, safety: false, ladders: LADDERS }

/** Every screen from the welcome on, as `after` walks them, answering each ladder question
 * from `answers` (then Skip). */
function walkAll(known: Known, start: Draft, answers: string[] = []): string[] {
  const seen = ['welcome']
  let draft = start
  for (let at: string | null = 'welcome'; at;) {
    const on = ladderAt(at, known, draft)
    if (on) {
      const given = draft.placement[on.ladder.slug] ?? []
      const answer = (answers.shift() ?? 'skip') as 'yes'
      draft = { ...draft, placement: { ...draft.placement, [on.ladder.slug]: [...given, answer] } }
    }
    at = after(at, known, draft)
    if (at) seen.push(at)
  }
  return seen
}

/** The ladder screens a walk asks, with the step each asks about. */
const asked = (known: Known, draft: Draft, answers: string[] = []) =>
  walkAll(known, draft, answers).filter((id) => id.startsWith('ladder:'))

test('with nothing on the server yet, every screen is asked in the ADR order', () => {
  const ladders = ['ladder:push-up:0', 'ladder:swing:0'] // each skipped
  expect(walkAll(ALL, NEW)).toEqual(ORDER.flatMap((s) => (s.id === 'ladders' ? ladders : [s.id])))
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
  expect(after('places', NONE, { ...NEW, places: 'gym' })).toBe('ladder:push-up:0')
  expect(after('places', NONE, { ...NEW, places: 'both' })).toBe('kit')
})

test('each screen carries its ADR number for the progress line', () => {
  expect(numberOf('welcome')).toBe(0)
  expect(numberOf(SAFETY[9])).toBe(3)
  expect(numberOf('howLong')).toBe(5)
  expect(numberOf('floor')).toBe(6)
  expect(numberOf('kit')).toBe(8)
  expect(numberOf('ladder:push-up:3')).toBe(9)
  expect(numberOf('days')).toBe(10)
  expect(numberOf('count')).toBe(12)
  expect(numberOf('nowhere')).toBe(0)
  expect(after('next', ALL, NEW)).toBeNull()
})

test('each ladder asks from the suggested level, up on a yes, until its walk is done', () => {
  // Nothing answered: level 4, the push-up's fourth step; Yes walks up to the fifth.
  expect(asked(NONE, NEW, ['yes', 'yes'])).toEqual([
    'ladder:push-up:0',
    'ladder:push-up:1',
    'ladder:swing:0',
  ])
  const at = (id: string, answers: Draft['placement']) =>
    ladderAt(id, NONE, { ...NEW, placement: answers })?.step.id
  expect(at('ladder:push-up:0', {})).toBe(13)
  expect(at('ladder:push-up:1', { 'push-up': ['yes'] })).toBe(14)
  expect(at('ladder:push-up:1', { 'push-up': ['no'] })).toBe(12)
  expect(at('ladder:push-up:1', { 'push-up': ['skip'] })).toBeUndefined() // done
  expect(at('ladder:rows:0', {})).toBeUndefined() // not a ladder
  expect(at('days', {})).toBeUndefined()
  // A lower suggested level starts lower: 75 or over is 2.
  const older = { ...NEW, about: { ...NOTHING_ANSWERED, age: '75+' as const } }
  expect(ladderAt('ladder:push-up:0', NONE, older)?.step.id).toBe(11)
})

test('locked steps are never asked: what is avoided, and kit missing at home', () => {
  const offFloor = { ...NEW, avoid: { ...NEW.avoid, avoid_floor: true } }
  expect(rungsOf(PUSH, offFloor).map((r) => r.open)).toEqual([false, true, true, false, true])
  expect(ladderAt('ladder:push-up:0', NONE, offFloor)?.step.id).toBe(12) // nearest below
  // No kit listed locks nothing; bodyweight only locks the 16 kg swing at home, not at the gym.
  expect(asked(NONE, NEW)).toContain('ladder:swing:0')
  expect(asked(NONE, { ...NEW, kit: [] })).toEqual(['ladder:push-up:0'])
  expect(asked(NONE, { ...NEW, kit: [], places: 'both' })).toEqual(['ladder:push-up:0'])
  expect(asked(NONE, { ...NEW, kit: [], places: 'gym' })).toContain('ladder:swing:0')
  const owned = { ...NEW, kit: [{ kit: 'kettlebell' as const, kg: 16, note: '' }] }
  expect(asked(NONE, owned)).toContain('ladder:swing:0')
})

test('after the last ladder come the days, the minutes and the count', () => {
  const none = { ...NONE, ladders: [] }
  expect(after('kit', none, NEW)).toBe('days')
  expect(after('ladder:swing:0', NONE, { ...NEW, placement: { swing: ['yes'] } })).toBe('days')
  expect(after('days', NONE, NEW)).toBe('minutes')
  expect(after('minutes', NONE, NEW)).toBe('count')
  expect(after('count', NONE, NEW)).toBe('next')
})

test('a step with no level is never where a walk starts, but is asked on the way', () => {
  const ladder: WalkLadder = { ...PUSH, steps: [step(10, 1), step(11, null), step(12, 3)] }
  const known = { ...NONE, ladders: [ladder] }
  const at = (k: number, answers: Draft['placement']) =>
    ladderAt(`ladder:push-up:${k}`, known, { ...NEW, placement: answers })?.step.id
  expect(at(0, {})).toBe(12) // level 4: the nearest below with a level
  expect(at(1, { 'push-up': ['no'] })).toBe(11)
})
