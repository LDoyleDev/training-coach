import { expect, test } from 'vitest'
import {
  DEFAULTS,
  activeSeconds,
  buildSchedule,
  cueFor,
  formatClock,
  formatDuration,
  parseSetting,
  positionAt,
  roundsCompleted,
  sanitize,
  skip,
  totalSeconds,
  type HiitSettings,
} from './logic'

const plain = (s: Partial<HiitSettings>): HiitSettings => ({
  ...DEFAULTS,
  prepare: 0,
  setRest: 0,
  ...s,
})

// prepare 5, 2 sets of 2 cycles of 20/10, 30 between sets, cool down 60.
const TWO_SETS = plain({
  prepare: 5,
  work: 20,
  rest: 10,
  cycles: 2,
  sets: 2,
  setRest: 30,
  coolDown: 60,
})

const rows = (s: HiitSettings) =>
  buildSchedule(s).map((x) => [x.phase, x.cycle, x.set, x.start, x.end])

test('the defaults are one Tabata: 10 s prepare, 8 × 20 s on / 10 s off, 4:00 of work', () => {
  const schedule = buildSchedule(DEFAULTS)
  expect(schedule[0]).toMatchObject({ phase: 'prepare', start: 0, end: 10 })
  expect(schedule.filter((s) => s.phase === 'work')).toHaveLength(8)
  expect(schedule.filter((s) => s.phase === 'rest')).toHaveLength(7)
  expect(schedule).toHaveLength(16)
  expect(totalSeconds(schedule)).toBe(10 + 8 * 20 + 7 * 10)
})

test('sets repeat the cycles with a rest between sets, never after the last; then cool down', () => {
  expect(rows(TWO_SETS)).toEqual([
    ['prepare', 1, 1, 0, 5],
    ['work', 1, 1, 5, 25],
    ['rest', 1, 1, 25, 35],
    ['work', 2, 1, 35, 55],
    ['setRest', 2, 1, 55, 85],
    ['work', 1, 2, 85, 105],
    ['rest', 1, 2, 105, 115],
    ['work', 2, 2, 115, 135],
    ['coolDown', 2, 2, 135, 195],
  ])
  expect(totalSeconds(buildSchedule(TWO_SETS))).toBe(195)
})

test('sections of 0 seconds are left out', () => {
  expect(rows(plain({ work: 20, rest: 0, cycles: 3, sets: 2 })).map((r) => r[0])).toEqual([
    'work',
    'work',
    'work',
    'work',
    'work',
    'work',
  ])
  expect(totalSeconds(buildSchedule(plain({ work: 30, cycles: 1 })))).toBe(30)
  expect(totalSeconds([])).toBe(0)
})

test('the position is the section and the seconds left in it', () => {
  const schedule = buildSchedule(TWO_SETS)
  expect(positionAt(schedule, 0)).toMatchObject({ index: 0, remaining: 5, done: false })
  expect(positionAt(schedule, 5)).toMatchObject({ index: 1, remaining: 20 })
  expect(positionAt(schedule, 24.5).section.phase).toBe('work')
  expect(positionAt(schedule, 60).section).toMatchObject({ phase: 'setRest', set: 1 })
  expect(positionAt(schedule, 195)).toMatchObject({ done: true, remaining: 0, index: 9 })
})

test('skip forward goes to the next section; back restarts, or goes back when just started', () => {
  const schedule = buildSchedule(TWO_SETS)
  expect(skip(schedule, 10, 'forward')).toBe(25)
  expect(skip(schedule, 190, 'forward')).toBe(195) // from cool down to the end
  expect(skip(schedule, 195, 'forward')).toBe(195) // nothing after the end
  expect(skip(schedule, 10, 'back')).toBe(5) // 5 s into work: restart it
  expect(skip(schedule, 26, 'back')).toBe(5) // 1 s into rest: the work before
  expect(skip(schedule, 1, 'back')).toBe(0) // the first section has nothing before it
  expect(skip(schedule, 195, 'back')).toBe(135) // from the end: back into cool down
})

test('a round counts once its work has ended, across sets, unless it was skipped', () => {
  const schedule = buildSchedule(TWO_SETS)
  expect(roundsCompleted(schedule, 4)).toBe(0)
  expect(roundsCompleted(schedule, 24)).toBe(0) // mid-work, round 1
  expect(roundsCompleted(schedule, 25)).toBe(1)
  expect(roundsCompleted(schedule, 70)).toBe(2) // rest between sets
  expect(roundsCompleted(schedule, 120)).toBe(3)
  expect(roundsCompleted(schedule, 195)).toBe(4)
  expect(roundsCompleted(schedule, 195, new Set([1, 5]))).toBe(2)
})

test('seconds done leave out the prepare count and stop at the end', () => {
  const schedule = buildSchedule(TWO_SETS)
  expect(activeSeconds(schedule, 3)).toBe(0)
  expect(activeSeconds(schedule, 25)).toBe(20)
  expect(activeSeconds(schedule, 999)).toBe(190)
  expect(activeSeconds(buildSchedule(plain({ cycles: 2 })), 30)).toBe(30)
})

test('voice cues: work, halfway, last round, rest, cool down', () => {
  const schedule = buildSchedule(DEFAULTS) // prepare, then work 1 at index 1, rest at 2, ...
  const cues = schedule.map((_, i) => cueFor(schedule, i))
  expect(cues[0]).toBeNull()
  expect(cues[1]).toBe('Work')
  expect(cues[2]).toBe('Rest')
  expect(cues.filter((c) => c === 'Halfway')).toHaveLength(1)
  expect(cueFor(schedule, 9)).toBe('Halfway') // work 5 of 8: four done
  expect(cueFor(schedule, 15)).toBe('Last round')
  expect(cueFor(schedule, 99)).toBeNull()
  const two = buildSchedule(TWO_SETS)
  expect(cueFor(two, 4)).toBe('Rest') // between sets
  expect(cueFor(two, 8)).toBe('Cool down')
  expect(cueFor(buildSchedule(plain({ cycles: 1 })), 0)).toBe('Work') // one round: no "last"
})

test('settings typed in are kept inside their limits', () => {
  expect(parseSetting('cycles', '12', 8)).toBe(12)
  expect(parseSetting('cycles', '99', 8)).toBe(50)
  expect(parseSetting('work', '0', 20)).toBe(1)
  expect(parseSetting('rest', '0', 10)).toBe(0)
  expect(parseSetting('rest', '', 10)).toBe(10)
  expect(parseSetting('rest', 'abc', 10)).toBe(10)
})

test('settings from anywhere are cleaned: unknown or bad fields fall back to the defaults', () => {
  expect(sanitize(null)).toEqual(DEFAULTS)
  expect(sanitize({ work: 45.4, sets: 99, rest: 'x', cycles: Number.NaN })).toEqual({
    ...DEFAULTS,
    work: 45,
    sets: 20,
  })
})

test('durations and the clock read the way a timer does', () => {
  expect(formatDuration(230)).toBe('3:50')
  expect(formatDuration(5)).toBe('0:05')
  expect(formatDuration(3725)).toBe('1:02:05')
  expect(formatClock(19.2)).toBe('20')
  expect(formatClock(90)).toBe('1:30')
  expect(formatClock(-1)).toBe('0')
})
