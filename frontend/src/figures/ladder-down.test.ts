import { expect, test } from 'vitest'
import { blend, dist, heading, solve, type Joints, type Vec } from './body'
import { solveFront } from './front'
import { FIGURES } from './poses'
import { shapes } from './shapes'
import { figureFor } from './steps'

const ALONG = [0, 0.25, 0.5, 0.75, 1]
const poses = (slug: string, step: string): Joints[] => {
  const f = figureFor(slug, step)!
  return ALONG.map((t) => solve(blend(f.start, f.end, t)))
}
const bend = (a: Vec, b: Vec, c: Vec) => Math.abs(heading(a, b) - heading(b, c))
const same = (a: Vec, b: Vec) => expect(dist(a, b)).toBeLessThan(0.1)

// Each incline push-up's support, by its top: where the hands rest.
const INCLINES: [string, number][] = [
  ['Hands on a counter', 90],
  ['Hands on a table', 74],
  ['Hands on a chair seat against a wall', 45],
  ['Hands on a stair or low step', 18],
]

test('a push-up with the hands raised keeps them on the edge and the body in one line', () => {
  for (const [step, top] of INCLINES) {
    const all = poses('push-up', step)
    for (const j of all) {
      for (const arm of [j.armN, j.armF]) expect(arm.wrist[1] - top, step).toBeCloseTo(2.5, 1)
      same(j.legN.ball, all[0].legN.ball) // the feet stay put
      expect(bend(j.legN.ankle, j.hip, j.shoulder), `${step}: straight`).toBeLessThan(1)
    }
    const [up, down] = [all[0], all[4]]
    expect(dist(up.shoulder, up.armN.wrist), `${step}: arms straight`).toBeGreaterThan(52)
    expect(dist(down.shoulder, down.armN.wrist), `${step}: chest to the edge`).toBeLessThan(42)
  }
})

test('a push-up against the wall keeps the palms flat on it, the feet a step back', () => {
  const f = figureFor('push-up', 'Hands on a wall')!
  const wall = f.props!.wall!.x0
  const all = poses('push-up', 'Hands on a wall')
  for (const j of all) {
    expect(j.armN.wrist[0]).toBeCloseTo(wall - 3, 1)
    for (const arm of [j.armN, j.armF]) {
      expect(arm.wrist[0], 'at the wall').toBeLessThanOrEqual(wall)
      expect(arm.tip[0], 'fingers up the wall').toBeCloseTo(arm.wrist[0], 1)
    }
    same(j.legN.ball, all[0].legN.ball)
  }
  expect(wall - all[0].legN.ball[0], 'a step back').toBeGreaterThan(60)
  expect(all[4].shoulder[0], 'chest to the wall').toBeGreaterThan(all[0].shoulder[0] + 15)
})

test('a push-up on the knees pivots on them from knees to head in one line', () => {
  const all = poses('push-up', 'On the knees')
  for (const j of all) {
    expect(j.legN.knee[1], 'knees down').toBeCloseTo(5.4, 0)
    expect(bend(j.legN.knee, j.hip, j.shoulder), 'one line').toBeLessThan(1)
    same(j.armN.wrist, all[0].armN.wrist)
  }
  expect(all[4].shoulder[1], 'chest a fist above the floor').toBeLessThan(25)
  expect(all[4].shoulder[1]).toBeGreaterThan(12)
})

test('a split squat holding a chair keeps both feet and the hand where they are', () => {
  const lowest: Record<string, number> = {}
  for (const step of ['Holding a chair, short range', 'Holding a chair, full range']) {
    const all = poses('bulgarian-split-squat', step)
    const back = figureFor('bulgarian-split-squat', step)!.props!.chair!
    for (const j of all) {
      same(j.legN.ankle, all[0].legN.ankle)
      expect(j.legF.ball[1], `${step}: back foot on its toes`).toBeCloseTo(0, 0)
      expect(j.legF.heel[1], `${step}: heel up`).toBeGreaterThan(5)
      expect(j.armN.wrist[0] - back.x0, `${step}: hand on the chair back`).toBeCloseTo(2, 0)
    }
    lowest[step] = all[4].legF.knee[1]
  }
  expect(lowest['Holding a chair, full range'], 'back knee just above the floor').toBeLessThan(14)
  expect(lowest['Holding a chair, short range']).toBeGreaterThan(25)
})

test('the back foot on a low step stays on its edge as the back knee drops', () => {
  const top = figureFor('bulgarian-split-squat', 'Back foot on a low step')!.props!.step!.top
  const all = poses('bulgarian-split-squat', 'Back foot on a low step')
  for (const j of all) expect(j.legF.ball[1] - top).toBeCloseTo(0, 0)
  expect(all[4].legF.knee[1]).toBeLessThan(14)
})

test('a pull-up with the feet on a chair: hands on the bar, feet on the seat all the way', () => {
  const f = figureFor('pull-up', 'Feet on a chair')!
  const [bar, seat] = [f.props!.bar!, f.props!.chair!.seat]
  for (const j of poses('pull-up', 'Feet on a chair')) {
    for (const arm of [j.armN, j.armF]) expect(dist(arm.wrist, bar)).toBeLessThan(6)
    expect(j.legN.ball[1] - seat, 'on the seat').toBeGreaterThan(-0.75)
    expect(j.legN.ball[1] - seat).toBeLessThan(8)
  }
  const [low, high] = [solve(f.start), solve(f.end)]
  expect(high.head.c[1], 'chin over the bar').toBeGreaterThan(bar[1])
  expect(bend(low.hip, low.legN.knee, low.legN.ankle), 'knees bent').toBeGreaterThan(60)
})

test('scapular pulls hang on straight arms and rise a little', () => {
  const all = poses('pull-up', 'Scapular pulls')
  for (const j of all)
    expect(j.armN.elbow[1], 'arms up, straight').toBeGreaterThan(j.shoulder[1] + 25)
  expect(all[4].hip[1] - all[0].hip[1]).toBeGreaterThan(1.5)
  expect(all[4].hip[1] - all[0].hip[1]).toBeLessThan(8)
})

test('household loads replace the bell: a bag on the row and the curl, bottles on the curl', () => {
  const drawn = (slug: string, step: string) => {
    const f = figureFor(slug, step)!
    return { f, drawn: shapes(f.start, f.props, f.order) }
  }
  for (const [slug, step] of [
    ['kb-row', 'A bag, about 4 kg'],
    ['kb-curl', 'A bag, 2-4 kg'],
  ]) {
    const { f } = drawn(slug, step)
    expect(f.props!.bag, step).toBe('near')
    expect(f.props!.bell, step).toBeUndefined()
  }
  const bottles = drawn('kb-curl', 'Water bottles, about 1 kg')
  expect(bottles.f.props).toEqual({ bottles: true })
  expect(bottles.drawn.filter((s) => s.kind === 'path' && s.tone === 'prop')).toHaveLength(4)
  // One arm at a time with a bag: the far arm hangs while the near one curls.
  const [low, high] = poses('kb-curl', 'A bag, 2-4 kg').filter((_, i) => i % 4 === 0)
  same(low.armF.wrist, high.armF.wrist)
  expect(high.armN.wrist[1]).toBeGreaterThan(low.armN.wrist[1] + 40)
  expect(FIGURES['kb-curl'].props!.bell).toBe('near') // the bell's steps keep the bell
})

test('a calf raise on both legs keeps both feet down; on the floor the balls stay put', () => {
  const flat = poses('calf-raise', 'Both legs, hands on a wall')
  for (const j of flat) {
    for (const leg of [j.legN, j.legF]) expect(leg.ball[1]).toBeCloseTo(0, 0)
    expect(dist(j.legN.ball, flat[0].legN.ball)).toBeLessThan(1)
  }
  expect(flat[4].legN.heel[1], 'heels up').toBeGreaterThan(flat[0].legN.heel[1] + 8)
  expect(figureFor('calf-raise', 'Both legs, hands on a wall')!.inset).toBeUndefined()
  for (const j of poses('calf-raise', 'Both legs, on a step')) {
    expect(j.legF.ball[0] - j.legN.ball[0], 'feet side by side').toBeCloseTo(3, 1)
    expect(j.legF.ball[1]).toBeCloseTo(j.legN.ball[1], 1)
  }
})

test('a Copenhagen plank with the bottom foot helping keeps that foot on the floor', () => {
  const f = figureFor('copenhagen-plank', 'Knee on a chair, bottom foot helping')!
  for (const j of poses('copenhagen-plank', 'Knee on a chair, bottom foot helping')) {
    expect(j.legF.ankle[1]).toBeCloseTo(5, 1)
    expect(j.legF.knee[1], 'the knee off the floor').toBeGreaterThan(5)
  }
  for (const t of ALONG) {
    const j = solveFront(blend(f.front!.start, f.front!.end, t))
    expect(j.legL.end[1], 'from the front too').toBeCloseTo(5, 1)
    expect(j.legL.mid[1]).toBeGreaterThan(5)
  }
  expect(solve(f.end).hip[1], 'hips up').toBeGreaterThan(solve(f.start).hip[1] + 15)
})
