import { expect, test } from 'vitest'
import type { FlowMove } from '../api'
import { at, clock, cues, jump, minutesDone, schedule, totalSeconds } from './flow'

const move = (slug: string, seconds: number, per_side = false): FlowMove => ({
  slug,
  name: slug,
  seconds,
  per_side,
  target: 't',
  start: 's',
  end: 'e',
  cues: ['c'],
  breathing: 'b',
  easier: 'x',
  pacing: 'p',
})

// bridge 0-60, lunge 60-150 (switch at 105), cat 150-210.
const SECTIONS = schedule([move('bridge', 60), move('lunge', 45, true), move('cat', 60)])

test('a one-sided movement takes its time on each side, switching halfway', () => {
  expect(SECTIONS).toEqual([
    { index: 0, start: 0, end: 60, half: null },
    { index: 1, start: 60, end: 150, half: 105 },
    { index: 2, start: 150, end: 210, half: null },
  ])
  expect(totalSeconds(SECTIONS)).toBe(210)
  expect(totalSeconds([])).toBe(0)
})

test('where the flow is: the time left on this side, and next up near the end', () => {
  expect(at(SECTIONS, 0)).toEqual({ index: 0, done: false, left: 60, side: null, nextUp: false })
  expect(at(SECTIONS, 55.5).nextUp).toBe(true)
  expect(at(SECTIONS, 70)).toMatchObject({ index: 1, side: 1, left: 35, nextUp: false })
  expect(at(SECTIONS, 105)).toMatchObject({ index: 1, side: 2, left: 45 })
  expect(at(SECTIONS, 206).nextUp).toBe(false) // the last movement has nothing after it
  expect(at(SECTIONS, 210)).toMatchObject({ index: 2, done: true, left: 0 })
})

test('the sounds due between two ticks, in order', () => {
  expect(cues(SECTIONS, 0, 56)).toEqual([])
  expect(cues(SECTIONS, 56, 61)).toEqual(['count', 'count', 'count', 'next'])
  expect(cues(SECTIONS, 104.9, 105.1)).toEqual(['switch'])
  expect(cues(SECTIONS, 208.5, 212)).toEqual(['count', 'finish'])
  expect(cues(SECTIONS, 57, 57)).toEqual([]) // nothing twice
})

test('Skip goes to the next start; Back to this start, or the one before just after it', () => {
  expect(jump(SECTIONS, 20, 'forward')).toBe(60)
  expect(jump(SECTIONS, 200, 'forward')).toBe(210)
  expect(jump(SECTIONS, 210, 'forward')).toBe(210)
  expect(jump(SECTIONS, 80, 'back')).toBe(60)
  expect(jump(SECTIONS, 61, 'back')).toBe(0)
  expect(jump(SECTIONS, 1, 'back')).toBe(0) // nothing before the first
  expect(jump(SECTIONS, 210, 'back')).toBe(150)
})

test('minutes moved round to the nearest, at least one once started', () => {
  expect([minutesDone(0), minutesDone(10), minutesDone(89), minutesDone(600)]).toEqual([
    0, 1, 1, 10,
  ])
  expect([clock(65), clock(5), clock(-1)]).toEqual(['1:05', '0:05', '0:00'])
})
