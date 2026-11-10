import { expect, test } from 'vitest'
import shared from './cycle-cases.json?raw'
import {
  type Key,
  type Slot,
  add,
  applied,
  cannotAdd,
  days,
  move,
  problem,
  remove,
  restDaysLeft,
  split,
  suggestedAfter,
  withRest,
} from './cycleLogic'

// The cases backend/tests/domain/test_cycle.py reads too, so the two copies can't drift.
type Pairs = [Key, number][]
interface Cases {
  split: { rest_after: number; before: number; new: number }[]
  add: {
    case: string
    cycle: Pairs
    after: Key | null
    suggested: Key
    result: Pairs
    days: number
  }[]
  remove: { case: string; cycle: Pairs; key: Key; result: Pairs; days: number }[]
  move: { case: string; cycle: Pairs; key: Key; by: number; result: Pairs }[]
  problem: { case: string; cycle: Pairs; problem: string | null }[]
  cannot_add: { case: string; cycle: Pairs; reason: string | null }[]
  applied: {
    case: string
    before: Pairs
    draft: Pairs
    pointer: number
    queued: number[]
    last_done: number | null
    then: {
      pointer: Key
      queued: number[]
      added: string[]
      removed: number[]
      moved: number[]
      last_rest: number | null
      days: number
      changed: boolean
    }
  }[]
}
const cases = JSON.parse(shared) as Cases & {
  rest_days_left: { case: string; rest_after: number; gone: number; left: number }[]
}

/** [key, rest_after] pairs as the JSON writes a cycle. */
const cycleOf = (pairs: Pairs): Slot[] => pairs.map(([key, restAfter]) => ({ key, restAfter }))

const OWNER = cycleOf([10, 20, 30, 40, 50, 60, 70].map((k) => [k, 0]))

test.each(cases.split)('$rest_after rest days', ({ rest_after, before, new: fresh }) => {
  expect(split(rest_after)).toEqual([before, fresh])
})

test.each(cases.add)('add: $case', ({ cycle, after, suggested, result, days: n }) => {
  expect(suggestedAfter(cycleOf(cycle))).toBe(suggested)
  const found = add(cycleOf(cycle), 'n1', after)
  expect(found).toEqual(cycleOf(result))
  expect(days(found)).toBe(n)
})

test.each(cases.remove)('remove: $case', ({ cycle, key, result, days: n }) => {
  const found = remove(cycleOf(cycle), key)
  expect(found).toEqual(cycleOf(result))
  expect(days(found)).toBe(n)
})

test.each(cases.move)('move: $case', ({ cycle, key, by, result }) => {
  expect(move(cycleOf(cycle), key, by)).toEqual(cycleOf(result))
})

test.each(cases.problem)('problem: $case', ({ cycle, problem: reason }) => {
  expect(problem(cycleOf(cycle))).toBe(reason)
})

test.each(cases.cannot_add)('cannot add: $case', ({ cycle, reason }) => {
  expect(cannotAdd(cycleOf(cycle))).toBe(reason)
})

test.each(cases.applied)('applied: $case', (c) => {
  const found = applied(
    cycleOf(c.before),
    cycleOf(c.draft),
    { pointer: c.pointer, queued: c.queued },
    c.last_done,
  )
  const then = c.then
  expect(found.cycle).toEqual(cycleOf(c.draft))
  expect(found.pointer).toBe(then.pointer)
  expect(found.queued).toEqual(then.queued)
  expect(found.added).toEqual(then.added)
  expect(found.removed).toEqual(then.removed)
  expect(found.moved).toEqual(then.moved)
  expect(found.lastRest).toBe(then.last_rest)
  expect(found.days).toBe(then.days)
  expect(found.changed).toBe(then.changed)
})

test('positions follow the new order', () => {
  const found = applied(OWNER, add(OWNER, 'n1', 30), { pointer: 40, queued: [] }, 30)
  expect(found.positions).toEqual(
    new Map<Key, number>([
      [10, 0],
      [20, 1],
      [30, 2],
      ['n1', 3],
      [40, 4],
      [50, 5],
      [60, 6],
      [70, 7],
    ]),
  )
})

test('a rest day set on one session', () => {
  expect(withRest(OWNER, 30, 2)[2]).toEqual({ key: 30, restAfter: 2 })
  expect(days(withRest(OWNER, 30, 2))).toBe(9)
})

test('a pointer outside the plan starts the new cycle', () => {
  expect(applied(OWNER, OWNER.slice(1), { pointer: 99, queued: [] }, null).pointer).toBe(20)
})

test('a session done last that was never in the cycle has no rest places', () => {
  expect(applied(OWNER, OWNER, { pointer: 10, queued: [] }, 99).lastRest).toBeNull()
})

test('a draft over a limit is not applied', () => {
  expect(() => applied(OWNER, [], { pointer: 10, queued: [] }, null)).toThrow(
    'at least one session',
  )
})

test('a draft naming a session not in the plan is not applied', () => {
  const draft = [...OWNER, { key: 99, restAfter: 0 }]
  expect(() => applied(OWNER, draft, { pointer: 10, queued: [] }, null)).toThrow(
    'session 99 is not in the plan',
  )
})

test.each<Key>([99, 'n9'])("an unknown session can't be edited: %s", (key) => {
  expect(() => remove(OWNER, key)).toThrow('is not in the cycle')
})

test('an unknown key reads as Python writes it', () => {
  expect(() => move(OWNER, 'n9', 1)).toThrow("session 'n9' is not in the cycle")
  expect(() => withRest(OWNER, 99, 1)).toThrow('session 99 is not in the cycle')
})

test('an empty cycle has no suggestion', () => {
  expect(() => suggestedAfter([])).toThrow('no sessions')
})

test('the id 1 and a new key "1" are different sessions', () => {
  const cycle = cycleOf([
    [1, 0],
    ['1', 0],
  ])
  expect(problem(cycle)).toBeNull()
  expect(applied(cycle.slice(0, 1), cycle, { pointer: 1, queued: [] }, null).added).toEqual(['1'])
})

test("the editor's steps leave the cycle they were given as it was", () => {
  const cycle = cycleOf([
    [1, 1],
    [2, 1],
    [3, 2],
  ])
  const copy = structuredClone(cycle)
  add(cycle, 'n1')
  remove(cycle, 1)
  move(cycle, 3, -1)
  withRest(cycle, 2, 4)
  applied(cycle, cycle.slice(1), { pointer: 1, queued: [] }, 3)
  expect(cycle).toEqual(copy)
})

test.each(cases.rest_days_left)('$case', ({ rest_after, gone, left }) => {
  expect(restDaysLeft(rest_after, gone)).toBe(left)
})
