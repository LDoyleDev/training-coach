import { expect, test } from 'vitest'
import {
  LEAD_IN,
  buildSchedule,
  formatClock,
  formatDuration,
  parseSetting,
  positionAt,
  roundsCompleted,
  workoutSeconds,
} from './logic'

const S = { rounds: 3, work: 20, rest: 10 }

test('the schedule is a lead-in, then work and rest in turn, with no rest after the last round', () => {
  expect(buildSchedule(S).map((s) => [s.phase, s.round, s.start, s.end])).toEqual([
    ['ready', 1, 0, 3],
    ['work', 1, 3, 23],
    ['rest', 1, 23, 33],
    ['work', 2, 33, 53],
    ['rest', 2, 53, 63],
    ['work', 3, 63, 83],
  ])
})

test('rest 0 means back-to-back work sections', () => {
  const schedule = buildSchedule({ rounds: 3, work: 20, rest: 0 })
  expect(schedule.map((s) => s.phase)).toEqual(['ready', 'work', 'work', 'work'])
  expect(schedule.at(-1)?.end).toBe(LEAD_IN + 60)
})

test('total duration counts the gaps between rounds, not the lead-in', () => {
  expect(workoutSeconds(S)).toBe(80)
  expect(workoutSeconds({ rounds: 8, work: 20, rest: 10 })).toBe(230)
  expect(workoutSeconds({ rounds: 1, work: 30, rest: 10 })).toBe(30)
  expect(buildSchedule(S).at(-1)?.end).toBe(LEAD_IN + workoutSeconds(S))
})

test('the position is the section and the seconds left in it', () => {
  const schedule = buildSchedule(S)
  expect(positionAt(schedule, 0)).toMatchObject({ index: 0, remaining: 3, done: false })
  expect(positionAt(schedule, 3)).toMatchObject({ index: 1, remaining: 20 })
  expect(positionAt(schedule, 22.5).section.phase).toBe('work')
  expect(positionAt(schedule, 23).section).toMatchObject({ phase: 'rest', round: 1 })
  expect(positionAt(schedule, 83)).toMatchObject({ done: true, remaining: 0 })
})

test('a round counts once its work has ended, whether stopped mid-work or mid-rest', () => {
  const schedule = buildSchedule(S)
  expect(roundsCompleted(schedule, 2)).toBe(0)
  expect(roundsCompleted(schedule, 22)).toBe(0) // mid-work, round 1
  expect(roundsCompleted(schedule, 23)).toBe(1) // work just ended
  expect(roundsCompleted(schedule, 30)).toBe(1) // mid-rest
  expect(roundsCompleted(schedule, 40)).toBe(1) // mid-work, round 2
  expect(roundsCompleted(schedule, 83)).toBe(3)
})

test('settings typed in are kept inside their limits', () => {
  expect(parseSetting('rounds', '12', 8)).toBe(12)
  expect(parseSetting('rounds', '99', 8)).toBe(30)
  expect(parseSetting('work', '2', 20)).toBe(5)
  expect(parseSetting('rest', '0', 10)).toBe(0)
  expect(parseSetting('rest', '', 10)).toBe(10)
  expect(parseSetting('rest', 'abc', 10)).toBe(10)
})

test('durations and the clock read the way a timer does', () => {
  expect(formatDuration(230)).toBe('3:50')
  expect(formatDuration(5)).toBe('0:05')
  expect(formatClock(19.2)).toBe('20')
  expect(formatClock(90)).toBe('1:30')
  expect(formatClock(-1)).toBe('0')
})
