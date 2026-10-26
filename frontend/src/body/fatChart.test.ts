import { expect, test } from 'vitest'
import { FAT_BOX, fatChart } from './fatChart'

const left = FAT_BOX.left
const right = FAT_BOX.width - FAT_BOX.right
const top = FAT_BOX.top
const bottom = FAT_BOX.height - FAT_BOX.bottom

test('nothing to draw', () => {
  expect(fatChart([], [])).toBeNull()
})

test('both lines share one axis and one time span, oldest on the left', () => {
  const found = fatChart(
    [
      { on: '2026-10-21', value: 18 },
      { on: '2026-10-01', value: 20 },
    ],
    [{ on: '2026-10-11', value: 22.4 }],
  )!
  expect(found.low).toBe(18)
  expect(found.high).toBe(23)
  expect(found.scale.dots.map((d) => d.point.on)).toEqual(['2026-10-01', '2026-10-21'])
  expect(found.scale.dots[0].x).toBe(left)
  expect(found.scale.dots[1].x).toBe(right)
  expect(found.tape.dots[0].x).toBeCloseTo((left + right) / 2)
  expect(found.scale.dots[1].y).toBe(bottom) // 18 is the bottom
  expect(found.scale.line).not.toBe('')
  expect(found.tape.line).toBe('') // one point: a dot, no line
})

test('a flat run gets room above and below, and one day sits in the middle', () => {
  const found = fatChart([{ on: '2026-10-21', value: 18.2 }], [])!
  expect([found.low, found.high]).toEqual([18, 20])
  expect(found.scale.dots[0].x).toBe((left + right) / 2)
  expect(found.scale.dots[0].y).toBeGreaterThan(top)
  expect(found.scale.dots[0].y).toBeLessThan(bottom)
  expect(found.start).toEqual(found.end)
})
