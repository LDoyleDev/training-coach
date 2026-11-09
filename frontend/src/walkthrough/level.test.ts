import { describe, expect, test } from 'vitest'
import { NOTHING_ANSWERED, suggestedLevel, type About, type AgeBand } from './level'

const with_ = (a: Partial<About>): About => ({ ...NOTHING_ANSWERED, ...a })
// Someone who answers every question the most able way.
const ABLE = with_({
  age: '18-34',
  often: 'three_plus',
  effort: 'breathless',
  howLong: 'over_30',
  chair: true,
  stairs: true,
  walk: true,
  floor: true,
})

describe('the suggested level, first match wins (ADR-0092)', () => {
  test.each<[string, Partial<About>, number]>([
    // Line 1: can't stand from a chair without hands, or can't walk 10 minutes.
    ['no chair', { chair: false }, 1],
    ['no walk', { walk: false }, 1],
    ['no chair beats every later line', { chair: false, stairs: false, often: 'one_two' }, 1],
    // Line 2: can't climb a flight of stairs, or exercises under once a week or not now.
    ['no stairs', { stairs: false }, 2],
    ['not at the moment', { often: 'not_now' }, 2],
    ['under once a week', { often: 'under_weekly' }, 2],
    ['line 2 beats line 3', { stairs: false, effort: 'talk', howLong: 'under_10' }, 2],
    // Line 3: 1-2 times a week, or only at talking effort, or for under 10 minutes.
    ['1-2 times a week', { often: 'one_two' }, 3],
    ['talking effort', { effort: 'talk' }, 3],
    ['under 10 minutes', { howLong: 'under_10' }, 3],
    // Otherwise 4, never higher.
    ['all the most able answers', {}, 4],
    ['10-30 minutes is not a line', { howLong: '10_30' }, 4],
    // The floor question picks no level (it marks "Keep me off the floor" suggested).
    ['no floor', { floor: false }, 4],
  ])('%s', (_, answers, level) => {
    expect(suggestedLevel({ ...ABLE, ...answers })).toBe(level)
  })

  test('a skipped question matches no line, so it lowers nothing', () => {
    expect(suggestedLevel(NOTHING_ANSWERED)).toBe(4)
    expect(suggestedLevel(with_({ often: 'one_two' }))).toBe(3)
    expect(suggestedLevel(with_({ chair: true, walk: null, stairs: null }))).toBe(4)
  })
})

describe('age caps the level', () => {
  test.each<[AgeBand, number, number, number]>([
    // band, able, line 3, line 1
    ['18-34', 4, 3, 1],
    ['35-49', 4, 3, 1],
    ['50-64', 4, 3, 1],
    ['65-74', 3, 3, 1],
    ['75+', 2, 2, 1],
  ])('%s', (age, able, three, one) => {
    expect(suggestedLevel({ ...ABLE, age })).toBe(able)
    expect(suggestedLevel({ ...ABLE, age, effort: 'talk' })).toBe(three)
    expect(suggestedLevel({ ...ABLE, age, chair: false })).toBe(one)
  })

  test('a skipped age caps nothing', () => {
    expect(suggestedLevel({ ...ABLE, age: null })).toBe(4)
  })
})
