import { expect, test } from 'vitest'
import type { Guided, GuidedItem } from '../api'
import {
  chosenIn,
  fromKept,
  kgText,
  loadFor,
  partnerOf,
  restTitle,
  saveChoice,
  savedChoice,
  shown,
  stepOf,
  summary,
  timed,
  toDone,
  unweighed,
  unitText,
  valueFor,
  versus,
} from './logic'

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
  muscles: [],
  parts: [],
  last_set_amrap: false,
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
  expect(values['0:1']).toEqual({ left: 6, right: 6, split: false, confirmed: true })
  expect(values['1:1']).toEqual({ left: 5, right: 4, split: true, confirmed: true })
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

test('set times go to the server and come back with the set (ADR-0061)', () => {
  const at = { started_at: '2026-10-20T16:00:00.000Z', done_at: '2026-10-20T16:00:40.000Z' }
  const done = toDone(session, {
    '0:1': { left: 6, right: 6, split: false, ...at },
    '1:1': { left: 5, right: 5, split: false, started_at: at.started_at }, // half: not sent
  })
  expect(done).toEqual([
    { item: 0, set_no: 1, left: 6, right: null, ...at },
    { item: 1, set_no: 1, left: 5, right: null },
  ])
  const values = fromKept({
    template_id: 1,
    position: 1,
    first: [],
    revision: 1,
    saved: false,
    sets: [{ item: 0, set_no: 1, left: 6, right: null, ...at }],
  })
  expect(values['0:1']).toEqual({ left: 6, right: 6, split: false, confirmed: true, ...at })
})

test('a set is timed from its screen to its confirm, and keeps its first times', () => {
  const shown = Date.parse('2026-10-20T16:00:00Z')
  const first = timed({ left: 6, right: 6, split: false }, shown, shown + 40_000)
  expect(first).toMatchObject({
    started_at: '2026-10-20T16:00:00.000Z',
    done_at: '2026-10-20T16:00:40.000Z',
  })
  expect(timed({ ...first, left: 5 }, shown + 90_000, shown + 99_000)).toEqual({
    ...first,
    left: 5,
  })
  // A screen time after the confirm (a clock change) never makes a negative set.
  expect(timed({ left: 6, right: 6, split: false }, shown, shown - 5_000).started_at).toBe(
    '2026-10-20T15:59:55.000Z',
  )
})

test('the rest title says switch inside a pair and rest otherwise', () => {
  const set = { item: 0, set_no: 1, target: 8, rest_seconds: 15, switch: true }
  expect(restTitle(set, 'Rows')).toBe('Switch to Rows · 15 s')
  expect(restTitle({ ...set, rest_seconds: 90, switch: false }, 'Rows')).toBe('Rest · 90 s')
  expect(restTitle(undefined, 'Rows')).toBe('Rest')
})

test('a loaded set keeps its weight, starts where it should, and shows it (ADR-0072)', () => {
  const load = (carried: boolean) => ({
    kit: 'barbell' as const,
    increment: 2.5,
    kg: [40, 45],
    carried,
  })
  const lifted = (carried: boolean) =>
    ({
      items: [item({ name: 'Bench', targets: [5, 5], load: load(carried) }), item({ name: 'Dip' })],
      order: [
        { item: 0, set_no: 1, target: 5 },
        { item: 0, set_no: 2, target: 5 },
        { item: 1, set_no: 1, target: 5 },
      ],
    }) as unknown as Guided
  const values = fromKept({
    template_id: 1,
    position: 1,
    first: [],
    revision: 1,
    saved: false,
    sets: [{ item: 0, set_no: 1, left: 5, right: null, load_kg: 42.5 }],
  })
  expect(values['0:1'].load_kg).toBe(42.5)
  expect(loadFor(lifted(true), values, 0, 1)).toBe(42.5) // what was confirmed
  expect(loadFor(lifted(true), values, 0, 2)).toBe(45) // the same set last time
  expect(loadFor(lifted(false), values, 0, 2)).toBe(42.5) // a first time follows today's set
  expect(loadFor(lifted(false), {}, 0, 2)).toBe(45)
  expect(loadFor(lifted(true), values, 1, 1)).toBeUndefined()
  const withDip = { ...values, '1:1': { left: 8, right: 8, split: false, load_kg: 10 } }
  expect(toDone(lifted(true), withDip)).toEqual([
    { item: 0, set_no: 1, left: 5, right: null, load_kg: 42.5 },
    { item: 1, set_no: 1, left: 8, right: null }, // no weight on a step without load
  ])
  expect(summary(lifted(true), values)[0].done).toBe(`5 at ${kgText(42.5)}`)
  const two = { ...values, '0:2': { left: 4, right: 4, split: false, load_kg: 45 } }
  const different = `5 × ${kgText(42.5)} · 4 × ${kgText(45)}` // each set with its weight
  expect(summary(lifted(true), two)[0].done).toBe(different)
})

test('a taken suggestion shows the new weight and targets, from the tap alone', () => {
  const up = { kg: 45, targets: [8, 8] }
  const plan = {
    day: '2026-10-27',
    template_id: 3,
    items: [
      item({
        targets: [12, 12],
        load: { kit: 'barbell', increment: 2.5, kg: [42.5, 42.5], carried: true, suggested: up },
      }),
      item({ name: 'Dip' }),
    ],
    order: [
      { item: 0, set_no: 1, target: 12 },
      { item: 1, set_no: 1, target: 5 },
      { item: 0, set_no: 2, target: 12 },
    ],
  } as unknown as Guided
  expect(shown(plan, {})).toBe(plan) // nothing taken: as sent
  const taken = shown(plan, { 0: true })
  expect(taken.items[0].targets).toEqual([8, 8])
  expect(taken.items[0].load?.kg).toEqual([45, 45])
  expect(taken.order.map((s) => s.target)).toEqual([8, 5, 8])
  expect(chosenIn(plan, taken)).toEqual({ 0: true, 1: false })
  expect(shown(plan, { 0: false })).toBe(plan)
  expect(shown(plan, { 1: true })).toBe(plan) // no suggestion there to take
  expect(savedChoice(plan)).toEqual({})
  saveChoice(plan, { 0: true })
  expect(savedChoice(plan)).toEqual({ 0: true }) // a reload keeps the tap
  localStorage.setItem('tc.weights-taken.2026-10-27.3', 'not json')
  expect(savedChoice(plan)).toEqual({})
  localStorage.clear()
})

test('only sets never confirmed start afresh, a kept set without times included', () => {
  const kept = fromKept({
    template_id: 1,
    position: 1,
    first: [],
    revision: 1,
    saved: false,
    sets: [{ item: 0, set_no: 1, left: 6, right: null, load_kg: 40 }], // no set times
  })
  const touched = { ...kept, '0:2': { left: 7, right: 7, split: false, load_kg: 40 } }
  expect(Object.keys(unweighed(touched, 0))).toEqual(['0:1'])
})
