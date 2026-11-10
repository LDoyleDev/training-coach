import { describe, expect, test } from 'vitest'
import { firstAsk, walk, type CanDo, type Rung } from './walk'

/** A ladder from its levels, easiest first, every step open unless its index is in `locked`.
 * Ids are 10, 11, 12... so they can't be mistaken for indices. */
const ladder = (levels: number[], locked: number[] = []): Rung[] =>
  levels.map((level, i) => ({ id: 10 + i, level, open: !locked.includes(i) }))

const FIVE = ladder([1, 2, 3, 4, 5])

describe('the first question', () => {
  test.each<[string, Rung[], number, number | null]>([
    ['the step at the suggested level', FIVE, 3, 2],
    ['the first of two at that level', ladder([1, 2, 2, 3]), 2, 1],
    ['the nearest open step below when none is at the level', ladder([1, 2, 4, 5]), 3, 1],
    [
      'the nearest open step below when the one at it is locked',
      ladder([1, 2, 3, 4, 5], [2]),
      3,
      1,
    ],
    ['the split squat starts at 2: a level 1 asks its first step up', ladder([2, 3, 4]), 1, 1],
    ['level 1 on a ladder whose bottom is level 1: the next step up', FIVE, 1, 1],
    ['the level is above the top: the highest step below', FIVE, 9, 4],
    ['nothing open above the bottom: nothing asked', ladder([1, 2, 3], [1, 2]), 2, null],
    ['a one-step ladder: nothing asked', ladder([1]), 1, null],
  ])('%s', (_, rungs, level, first) => {
    expect(firstAsk(rungs, level)).toBe(first)
  })
})

describe('walking', () => {
  // [name, ladder, level, answers, next index asked (or null: done), placed index]
  test.each<[string, Rung[], number, CanDo[], number | null, number]>([
    ['nothing answered yet', FIVE, 3, [], 2, 0],
    ['yes walks up to the next step', FIVE, 3, ['yes'], 3, 2],
    ['yes, then no: the highest yes', FIVE, 3, ['yes', 'no'], null, 2],
    ['yes to the top: no cap going up', FIVE, 3, ['yes', 'yes', 'yes'], null, 4],
    ['no walks down to the step below', FIVE, 3, ['no'], 1, 0],
    ['no, then yes: placed on the yes', FIVE, 3, ['no', 'yes'], null, 1],
    ['no all the way: the bottom, which has no question', FIVE, 3, ['no', 'no'], null, 0],
    ['not sure counts as no', FIVE, 3, ['not_sure', 'yes'], null, 1],
    ['not sure going up ends the walk', FIVE, 3, ['yes', 'not_sure'], null, 2],
    ['skip leaves the bottom', FIVE, 3, ['skip'], null, 0],
    ['skip after a yes still leaves the bottom', FIVE, 3, ['yes', 'skip'], null, 0],
    ['answers past the end are ignored', FIVE, 3, ['yes', 'no', 'yes'], null, 2],
    ['walking up from the bottom on a level 1', FIVE, 1, ['yes', 'yes'], 3, 2],
    ['a no from the bottom start: the bottom', FIVE, 1, ['no'], null, 0],
  ])('%s', (_, rungs, level, answers, next, placed) => {
    const got = walk(rungs, level, answers)
    expect([got.next, got.placed]).toEqual([next, placed])
  })

  test('locked steps are never asked, up or down', () => {
    const locked = ladder([1, 2, 3, 4, 5, 6], [2, 4])
    expect(walk(locked, 4, []).next).toBe(3)
    expect(walk(locked, 4, ['yes']).next).toBe(5) // skips the locked 4
    expect(walk(locked, 4, ['no']).next).toBe(1) // skips the locked 2
    expect(walk(locked, 4, ['no', 'no'])).toMatchObject({ next: null, placed: 0 })
  })

  test('the steps asked are kept by id, with each answer, in order', () => {
    expect(walk(FIVE, 3, ['no', 'not_sure']).asked).toEqual([
      [12, 'no'],
      [11, 'not_sure'],
    ])
    expect(walk(FIVE, 3, ['yes', 'no', 'yes']).asked).toEqual([
      [12, 'yes'],
      [13, 'no'],
    ])
  })

  test('a ladder with nothing to ask is done at the bottom', () => {
    expect(walk(ladder([1]), 3, ['yes'])).toEqual({ next: null, placed: 0, asked: [] })
  })
})
