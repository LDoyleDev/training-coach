import { expect, test } from 'vitest'
import type { Guided, GuidedItem } from '../api'
import { fromKept, partnerOf, stepOf, summary, toDone, unitText, valueFor, versus } from './logic'

const item = (over: Partial<GuidedItem>): GuidedItem => ({
  slug: 'x',
  name: 'X',
  step: 's',
  summary: null,
  cue: null,
  unit: 'reps',
  per_side: false,
  pair: null,
  targets: [5],
  baseline: false,
  ...over,
})

const session = {
  items: [
    item({ name: 'A', pair: 1 }),
    item({ name: 'B', pair: 1, per_side: true }),
    item({ name: 'Hang', unit: 'seconds', targets: [30, 30] }),
  ],
  order: [
    { item: 0, set_no: 1, target: 5 },
    { item: 1, set_no: 1, target: 5 },
    { item: 2, set_no: 1, target: 30 },
    { item: 2, set_no: 2, target: 30 },
  ],
} as unknown as Guided

test('kept sets come back with their split', () => {
  const values = fromKept({
    template_id: 1,
    position: 2,
    first: [],
    revision: 1,
    saved: false,
    sets: [
      { item: 0, set_no: 1, left: 6, right: null },
      { item: 1, set_no: 1, left: 5, right: 4 },
    ],
  })
  expect(values['0:1']).toEqual({ left: 6, right: 6, split: false })
  expect(values['1:1']).toEqual({ left: 5, right: 4, split: true })
  expect(fromKept(null)).toEqual({})
})

test('only one-sided, split sets send a right value, in work order', () => {
  const done = toDone(session, {
    '2:1': { left: 30, right: 30, split: false },
    '1:1': { left: 5, right: 4, split: true },
    '0:1': { left: 6, right: 9, split: true }, // two-sided: right never sent
  })
  expect(done).toEqual([
    { item: 0, set_no: 1, left: 6, right: null },
    { item: 1, set_no: 1, left: 5, right: 4 },
    { item: 2, set_no: 1, left: 30, right: null },
  ])
})

test('values, steps, units and the target comparison', () => {
  expect(valueFor({}, 0, 1, 7)).toEqual({ left: 7, right: 7, split: false })
  expect(stepOf(item({}))).toBe(1)
  expect(stepOf(item({ unit: 'seconds' }))).toBe(5)
  expect(unitText(item({ unit: 'seconds' }), 30)).toBe('30 s')
  expect(unitText(item({ unit: 'minutes' }), 45)).toBe('45 min')
  expect(versus(5, 5)).toBe('on target')
  expect(versus(7, 5)).toBe('2 over')
  expect(versus(3, 5)).toBe('2 under')
})

test('the summary shows what was done against each target', () => {
  const rows = summary(session, {
    '0:1': { left: 5, right: 5, split: false },
    '2:1': { left: 25, right: 25, split: false },
  })
  expect(rows[0]).toEqual({ name: 'A', target: '5', done: '5', hit: true })
  expect(rows[1]).toMatchObject({ done: 'not done', hit: false })
  expect(rows[2]).toMatchObject({ target: '30 s · 30 s', done: '25 s', hit: false })
})

test('a paired exercise knows its partner', () => {
  expect(partnerOf(session, 0)?.name).toBe('B')
  expect(partnerOf(session, 2)).toBeNull()
})
