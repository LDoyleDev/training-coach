import { expect, test } from 'vitest'
import { at, jump, stretchCues, stretchSchedule, totalSeconds } from './flow'

const TIMING = { hold: 30, position: 15, release: 5 }

// Couch, one-sided, 2 rounds: into position 0-15, hold 15-45, let go 45-50, hold 50-80; the
// other side 80-95, 95-125, 125-130, 130-160. Fold, 3 rounds: 160-175, 175-205, 205-210,
// 210-240, 240-245, 245-275.
const { parts, stretches } = stretchSchedule(
  [
    { rounds: 2, per_side: true },
    { rounds: 3, per_side: false },
  ],
  TIMING,
)

const kinds = () => parts.map((p) => `${p.kind}:${p.end - p.start}`)

test('each side starts with getting into position; rounds on a side have a release between', () => {
  expect(kinds()).toEqual([
    ...['position:15', 'hold:30', 'release:5', 'hold:30'],
    ...['position:15', 'hold:30', 'release:5', 'hold:30'],
    ...['position:15', 'hold:30', 'release:5', 'hold:30', 'release:5', 'hold:30'],
  ])
  expect(parts.map((p) => p.side ?? '-').join('')).toBe('11112222------')
  expect(parts.filter((p) => p.kind === 'hold').map((p) => p.round)).toEqual([1, 2, 1, 2, 1, 2, 3])
  expect(parts.every((p, i) => i === 0 || p.start === parts[i - 1].end)).toBe(true)
})

test('the total is the holds plus the gaps: what the routine was built to fit', () => {
  // As the backend counts it: sides × (position + rounds × hold + (rounds - 1) × release).
  expect(totalSeconds(parts)).toBe(2 * (15 + 2 * 30 + 5) + (15 + 3 * 30 + 2 * 5))
  expect(totalSeconds(parts)).toBe(275)
  expect(stretches).toEqual([
    { index: 0, start: 0, end: 160, half: 80 },
    { index: 1, start: 160, end: 275, half: null },
  ])
  // A ten-minute routine of real steps comes to its own exact sum, nothing added.
  const ten = stretchSchedule(
    [
      { rounds: 2, per_side: true },
      { rounds: 2, per_side: true },
      { rounds: 2, per_side: true },
      { rounds: 3, per_side: false },
    ],
    TIMING,
  )
  expect(totalSeconds(ten.parts)).toBe(595) // the Legs routine at 10 min: inside 600
  expect(stretchSchedule([], TIMING)).toEqual({ parts: [], stretches: [] })
})

test('where it is: the part and its countdown, the side, and "next" in a stretch’s last 5 s', () => {
  expect(at(parts, 0)).toMatchObject({ index: 0, left: 15 })
  expect(parts[at(parts, 15).index].kind).toBe('hold')
  expect(at(parts, 15.2).left).toBe(30)
  expect(parts[at(parts, 46).index].kind).toBe('release')
  expect(at(stretches, 79)).toMatchObject({ index: 0, side: 1, nextUp: false })
  expect(at(stretches, 81)).toMatchObject({ index: 0, side: 2, nextUp: false })
  expect(at(stretches, 155)).toMatchObject({ index: 0, side: 2, nextUp: true })
  expect(at(stretches, 271).nextUp).toBe(false) // the last stretch: nothing after it
})

test('a sound at every change, none on Start, and finish at the end', () => {
  expect(stretchCues(parts, 0, 14.9)).toEqual([])
  expect(stretchCues(parts, 0, 15)).toEqual(['next']) // the hold starts
  expect(stretchCues(parts, 44.9, 45.1)).toEqual(['count']) // let go
  expect(stretchCues(parts, 49.9, 50.1)).toEqual(['next']) // hold again
  expect(stretchCues(parts, 79.9, 80.1)).toEqual(['switch']) // the other side
  expect(stretchCues(parts, 159.9, 160.1)).toEqual(['next']) // the next stretch
  expect(stretchCues(parts, 274.9, 275)).toEqual(['finish'])
  expect(stretchCues(parts, 274.9, 400)).toEqual(['finish'])
  expect(stretchCues(parts, 0, 275)).toEqual([
    ...['next', 'count', 'next', 'switch', 'next', 'count', 'next'],
    ...['next', 'next', 'count', 'next', 'count', 'next', 'finish'],
  ])
  expect(stretchCues([], 0, 10)).toEqual([])
})

test('Back and Skip go stretch by stretch', () => {
  expect(jump(stretches, 100, 'forward')).toBe(160)
  expect(jump(stretches, 170, 'back')).toBe(160)
  expect(jump(stretches, 161, 'back')).toBe(0) // only just started: the one before
  expect(jump(stretches, 200, 'forward')).toBe(275)
})
