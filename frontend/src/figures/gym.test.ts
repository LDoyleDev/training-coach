import { expect, test } from 'vitest'
import { blend, dist, solve, type Joints, type Vec } from './body'
import { GYM } from './gym'
import { FIGURES } from './poses'
import { shapes } from './shapes'
import { figureFor } from './steps'

const STEPS = [0, 0.25, 0.5, 0.75, 1]
/** Every pose of ``slug`` along its movement. */
const along = (slug: string) => STEPS.map((t) => solve(blend(GYM[slug].start, GYM[slug].end, t)))
const near = (a: readonly number[], b: readonly number[], within = 0.05) =>
  expect(Math.hypot(a[0] - b[0], a[1] - b[1])).toBeLessThan(within)
/** The angle at ``b`` between ``a`` and ``c``, in degrees. */
const angleAt = (a: readonly number[], b: readonly number[], c: readonly number[]) => {
  const turn = Math.atan2(c[1] - b[1], c[0] - b[0]) - Math.atan2(a[1] - b[1], a[0] - b[0])
  return Math.abs((((turn * 180) / Math.PI + 540) % 360) - 180)
}
/** Where a bar or a handle is held: the middle of the near fist. */
const fist = (j: Joints): Vec => [
  (j.armN.wrist[0] + j.armN.tip[0]) / 2,
  (j.armN.wrist[1] + j.armN.tip[1]) / 2,
]

test('the gym figures are figures', () => {
  for (const slug of Object.keys(GYM)) expect(FIGURES[slug], slug).toBe(GYM[slug])
})

test('a back squat keeps the bar on the upper back, over the middle of the feet', () => {
  for (const j of along('back-squat')) {
    const bar = fist(j)
    expect(dist(bar, j.neckBase), 'on the upper back').toBeLessThan(16)
    expect(Math.abs(bar[0] - 4), 'over the middle of the foot').toBeLessThan(8)
    expect(j.legN.heel[1], 'heels down').toBeLessThan(2)
  }
  const bottom = solve(GYM['back-squat'].end)
  expect(bottom.hip[1], 'as deep as the thighs level').toBeLessThan(bottom.legN.knee[1] + 5)
  const { pins } = GYM['back-squat'].props!.rack!
  expect(fist(bottom)[1], 'the safety bars just below the lowest point').toBeGreaterThan(pins)
  expect(fist(bottom)[1]).toBeLessThan(pins + 12)
})

test('a barbell is a plate behind the figure and the bar end in front', () => {
  const { start, props, order } = GYM['back-squat']
  const drawn = shapes(start, props, order)
  const plate = drawn.findIndex((s) => s.kind === 'ball' && s.r === 22.5)
  const body = drawn.findIndex((s) => s.kind === 'path' && s.tone === 'near')
  expect(plate).toBeGreaterThan(-1)
  expect(plate).toBeLessThan(body) // behind the body
  const end = drawn.at(-1)!
  expect(end.kind === 'ball' && end.r).toBe(2.6) // the bar's end, last
})

test('a Romanian deadlift hinges at the hips with the bar close to the legs', () => {
  for (const j of along('barbell-rdl')) {
    near(j.legN.ankle, [0, 7])
    expect(Math.abs(fist(j)[0] - j.legN.ankle[0]), 'bar over the feet').toBeLessThan(12)
    expect(fist(j)[1] - 22.5, 'plates off the floor').toBeGreaterThan(0)
  }
  const bottom = solve(GYM['barbell-rdl'].end)
  expect(bottom.hip[0], 'hips back').toBeLessThan(-20)
  expect(fist(bottom)[1], 'bar below the knees').toBeLessThan(bottom.legN.knee[1])
  expect(angleAt(bottom.hip, bottom.legN.knee, bottom.legN.ankle), 'knees soft').toBeGreaterThan(
    150,
  )
})

test('a hip thrust pivots on the upper back with the bar on the hips', () => {
  const { x1, top } = GYM['hip-thrust'].props!.bench!
  for (const j of along('hip-thrust')) {
    near(j.legN.ankle, [40, 7])
    expect(dist(fist(j), j.hip), 'bar on the hips').toBeLessThan(20)
    // the upper back rests on the bench's edge
    expect(Math.abs(j.shoulder[0] - x1)).toBeLessThan(10)
    expect(j.shoulder[1]).toBeGreaterThan(top)
    expect(j.shoulder[1]).toBeLessThan(top + 12)
  }
  const [low, high] = [solve(GYM['hip-thrust'].start), solve(GYM['hip-thrust'].end)]
  expect(high.hip[1] - low.hip[1], 'hips driven up').toBeGreaterThan(20)
  expect(angleAt(high.legN.knee, high.hip, high.shoulder), 'knees to shoulders').toBeGreaterThan(
    175,
  )
})

test('a 45° back extension hinges over the pad and stops in a straight line', () => {
  for (const j of along('back-extension-45')) {
    near(j.legN.ankle, [-61.4, 38.6])
    near(j.hip, [0, 100])
  }
  const [top, low] = [solve(GYM['back-extension-45'].start), solve(GYM['back-extension-45'].end)]
  expect(
    angleAt(top.shoulder, top.hip, top.legN.ankle),
    'no further than straight',
  ).toBeGreaterThan(175)
  expect(low.head.c[1], 'chest towards the floor').toBeLessThan(low.hip[1] - 40)
  const plated = figureFor('back-extension-45', 'Holding a plate')!
  const plate = shapes(plated.start, plated.props, plated.order).find(
    (s) => s.kind === 'ball' && s.r === 15,
  )
  expect(plate?.kind === 'ball' && dist([plate.c[0], -plate.c[1]], top.midChest)).toBeLessThan(20)
})
