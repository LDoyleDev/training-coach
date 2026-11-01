import { expect, test } from 'vitest'
import { BODY, blend, dist, heading, solve, type Pose, type Vec } from './body'
import { solveFront } from './front'
import { ENTRY_LOWER } from './entry-lower'
import { STAIR, WORKTOP, railAt, shapes, type Shape } from './shapes'
import { figureFor } from './steps'

const ALONG = [0, 0.25, 0.5, 0.75, 1]
const poses = (slug: string, step?: string) => {
  const f = figureFor(slug, step)!
  return ALONG.map((t) => solve(blend(f.start, f.end, t)))
}
const straight = (a: Vec, b: Vec, c: Vec) => Math.abs(heading(a, b) - heading(b, c))
const ys = (shape: Shape) =>
  shape.kind === 'path' ? [...shape.d.matchAll(/(-?[\d.]+) (-?[\d.]+)/g)].map((m) => -m[2]) : []

test('the stairs, their banister and a counter beside you are drawn behind the figure', () => {
  const pose: Pose = ENTRY_LOWER['step-up'].start
  const plain = shapes(pose).length
  const stairs = shapes(pose, { stair: { x: 12, rise: 18 } })
  expect(stairs).toHaveLength(plain + 1) // the three stairs in one outline
  expect(Math.max(...ys(stairs[0]))).toBe(3 * 18)
  const railed = shapes(pose, { stair: { x: 12, rise: 18, rail: true } })
  expect(railed).toHaveLength(plain + 3) // and the newel post and the rail
  expect(railAt({ x: 12, rise: 18 }, 12 + STAIR.run)).toBe(2 * 18 + STAIR.rail)
  const counter = shapes(pose, { worktop: [-40, 50] })
  expect(counter).toHaveLength(plain + 2) // the cupboard and the worktop
  expect(Math.max(...ys(counter[1]))).toBe(WORKTOP)
})

test('a step-up keeps the foot on the stair and stands tall on it', () => {
  for (const step of [undefined, 'One stair, hand on the rail', 'Low step, hand on a support']) {
    const f = figureFor('step-up', step)!
    const top = f.props!.stair?.rise ?? f.props!.step!.top
    for (const j of poses('step-up', step)) {
      expect(j.legN.heel[1] - top, `${step}: on the stair`).toBeCloseTo(1.5, 0)
      expect(
        Math.min(j.legF.heel[1], j.legF.tip[1]),
        'the back foot off the stair',
      ).toBeGreaterThan(-0.5)
      if (step === 'One stair, hand on the rail')
        expect(j.armN.wrist[1] - railAt(f.props!.stair!, j.armN.wrist[0])).toBeCloseTo(3, 0)
      if (step?.startsWith('Low')) expect(j.armN.wrist[0]).toBeCloseTo(f.props!.wall!.x0 - 4, 5)
    }
    const end = solve(f.end)
    expect(dist(end.hip, end.legN.ankle), 'standing tall').toBeGreaterThan(84)
    expect(end.legF.tip[0], 'the back foot behind the edge').toBeLessThan(12)
  }
  for (const step of ['One stair, holding a bag', 'One stair, holding 8 kg']) {
    const f = figureFor('step-up', step)!
    const drawn = shapes(f.start, f.props, f.order)
    const held = drawn.filter((s) => 'tone' in s && s.tone === 'bell')
    expect(held.length, step).toBeGreaterThan(0)
    for (const s of held)
      if (s.kind === 'ball') expect(-s.c[1] - s.r, 'clear of the stair').toBeGreaterThan(18)
  }
})

test('a plank ends in one straight line, the hands staying where they are put', () => {
  const cases: [string | undefined, number][] = [
    [undefined, 3],
    ['Hands on a counter', WORKTOP + 2.5],
    ['Hands on a table', 76.5],
    ['Hands on a chair seat against a wall', 47.5],
  ]
  for (const [step, top] of cases) {
    const f = figureFor('plank', step)!
    const hands = f.end.armN.at!
    for (const j of poses('plank', step)) {
      expect(dist(j.armN.wrist, hands), `${step}: hands put`).toBeLessThan(0.05)
      expect(j.armN.wrist[1]).toBeCloseTo(top, 5)
      expect(Math.min(j.legN.ball[1], j.legN.tip[1]), 'feet on the floor').toBeGreaterThan(-0.5)
    }
    const end = solve(f.end)
    expect(straight(end.legN.ankle, end.hip, end.shoulder), `${step}: one line`).toBeLessThan(2)
    expect(dist(end.hip, end.legN.ankle), 'legs straight').toBeGreaterThan(86)
    expect(end.legN.ball[1]).toBeCloseTo(0, 1)
  }
  const knees = solve(ENTRY_LOWER.plank.start)
  expect(knees.legN.knee[1], 'starts on the knees').toBeCloseTo(5.4, 0)
  const counter = figureFor('plank', 'Hands on a counter')!
  expect(counter.end.armN.at![0], 'on the edge').toBeGreaterThan(counter.props!.wall!.x0)
})

test('a knee plank pivots on the knees into one line; the reach lifts one hand', () => {
  for (const j of poses('plank', 'On the knees')) {
    expect(dist(j.legN.knee, [0.1, 5.4])).toBeLessThan(0.5)
    expect(j.armN.wrist[1]).toBeCloseTo(3, 5)
  }
  const end = solve(figureFor('plank', 'On the knees')!.end)
  expect(straight(end.legN.knee, end.hip, end.shoulder), 'knees to head').toBeLessThan(1)
  const reach = figureFor('plank', 'Full plank, arm reach')!
  const out = solve(reach.end)
  expect(out.armN.wrist[1], 'the hand off the floor').toBeGreaterThan(out.shoulder[1] - 10)
  expect(out.armN.wrist[0], 'reaching forward').toBeGreaterThan(out.shoulder[0] + 50)
  expect(out.armF.wrist[1], 'the other hand down').toBeCloseTo(3, 5)
  expect(reach.order!.at(-1)).toBe('armN')
})

test('a knee lift keeps the standing foot down and the hand on the counter; seated, on the seat', () => {
  const lift = ENTRY_LOWER['knee-lift']
  for (const j of poses('knee-lift')) {
    expect(dist(j.legF.ankle, [3, 7])).toBeLessThan(0.05)
    expect(j.armF.wrist[1] - WORKTOP).toBeCloseTo(2.5, 5)
  }
  const up = solve(lift.end)
  expect(Math.abs(up.legN.knee[1] - up.hip[1]), 'knee to hip height').toBeLessThan(3)
  const { seat } = figureFor('knee-lift', 'Seated march')!.props!.chair!
  for (const j of poses('knee-lift', 'Seated march')) {
    expect(j.hip[1] - seat, 'sat on the seat').toBeGreaterThan(6)
    expect(j.hip[1] - seat).toBeLessThan(12)
    expect(j.armN.wrist[1] - seat, 'hands on it').toBeCloseTo(4, 5)
    expect(j.legF.heel[1], 'the other foot down').toBeLessThan(2)
  }
  const march = solve(figureFor('knee-lift', 'Seated march')!.end)
  expect(march.legN.heel[1], 'a hand’s width up').toBeGreaterThan(8)
})

test('a seated toe lift keeps the heels down and lifts the toes', () => {
  for (const j of poses('toe-lift')) {
    expect(j.legN.heel[1], 'heels down').toBeLessThan(2)
    expect(j.hip[1] - 45, 'on the seat').toBeLessThan(12)
  }
  expect(solve(ENTRY_LOWER['toe-lift'].end).legN.tip[1], 'toes up').toBeGreaterThan(12)
})

test('a deadlift takes the bell from the floor, or the bag from its block, close to the legs', () => {
  const bellAt = (slug: string, step: string | undefined, t: number) => {
    const f = figureFor(slug, step)!
    const drawn = shapes(blend(f.start, f.end, t), f.props, f.order)
    return drawn.filter((s) => 'tone' in s && s.tone === 'bell')
  }
  const [low] = bellAt('deadlift', undefined, 0).filter((s) => s.kind === 'ball')
  if (low?.kind !== 'ball') throw new Error('a bell')
  expect(-low.c[1] - low.r, 'on the floor').toBeLessThan(1)
  expect(-low.c[1] - low.r).toBeGreaterThan(-0.5)
  for (const j of poses('deadlift')) expect(dist(j.armN.wrist, j.armF.wrist)).toBeLessThan(1.5)
  const books = figureFor('deadlift', 'A bag, from a block')!.props!.step!
  const [bag] = bellAt('deadlift', 'A bag, from a block', 0).filter((s) => s.kind === 'path')
  expect(Math.min(...ys(bag)), 'resting on the books').toBeCloseTo(books.top, 0)
  const top = solve(figureFor('deadlift', 'A bag, from a block')!.end)
  expect(top.armN.wrist[0] - top.hip[0], 'close to the legs').toBeLessThan(10)
})

test('balance: hands on the counter or just over it, feet together, then heel to toe', () => {
  for (const j of poses('balance')) expect(j.armN.wrist[1] - WORKTOP).toBeCloseTo(2.5, 5)
  const over = solve(figureFor('balance', 'Feet together, hands over the counter')!.end)
  expect(over.armN.wrist[1] - WORKTOP, 'just above it').toBeGreaterThan(6)
  for (const [step, gap] of [
    ['Half heel-to-toe, beside the counter', 17],
    ['Heel-to-toe, beside the counter', 22],
  ] as const) {
    const f = figureFor('balance', step)!
    const [together, apart] = [solve(f.start), solve(f.end)]
    expect(Math.abs(together.legN.ankle[0] - together.legF.ankle[0]), 'together').toBeLessThan(3)
    expect(apart.legN.ankle[0] - apart.legF.ankle[0], step).toBeCloseTo(gap - 2, 5)
    for (const j of [together, apart]) {
      expect(j.armF.wrist[1] - WORKTOP, 'a hand ready over it').toBeGreaterThan(6)
      for (const leg of [j.legN, j.legF]) expect(leg.heel[1]).toBeLessThan(2)
    }
    // From the front, the legs keep their length and the feet stand on the floor.
    for (const pose of [f.front!.start, f.front!.end]) {
      const j = solveFront(pose)
      for (const leg of [j.legL, j.legR]) {
        const [knee, ankle] = [leg.z[0], leg.z[1]]
        expect(Math.hypot(dist(leg.root, leg.mid), knee)).toBeCloseTo(BODY.thigh, 1)
        expect(Math.hypot(dist(leg.mid, leg.end), ankle - knee)).toBeCloseTo(BODY.shin, 1)
        expect(leg.end[1]).toBe(7)
      }
    }
    const end = solveFront(f.front!.end)
    expect(end.legL.z[1] - end.legR.z[1], 'one foot in front').toBe(gap)
  }
})

test('balance on one leg: the standing foot stays down, the other lifts', () => {
  for (const step of [
    'One leg, a fingertip on the counter',
    'One leg, beside the counter',
    'One leg, turning your head',
    'One leg, eyes closed',
  ]) {
    for (const j of poses('balance', step)) expect(j.legF.heel[1], step).toBeLessThan(2)
    const up = solve(figureFor('balance', step)!.end)
    expect(Math.min(up.legN.heel[1], up.legN.tip[1]), 'foot lifted').toBeGreaterThan(5)
    const hand = up.armF.wrist[1] - WORKTOP
    expect(hand > 5, `${step}: touching or not`).toBe(!step.includes('fingertip'))
  }
})

test('an interval walk swaps which leg and arm are forward', () => {
  const walk = ENTRY_LOWER['interval-walk']
  const [a, b] = [solve(walk.start), solve(walk.end)]
  expect(a.legN.ankle[0]).toBeGreaterThan(a.legF.ankle[0] + 40)
  expect(b.legF.ankle[0]).toBeGreaterThan(b.legN.ankle[0] + 40)
  expect(a.armF.wrist[0]).toBeGreaterThan(a.armN.wrist[0])
  expect(b.armN.wrist[0]).toBeGreaterThan(b.armF.wrist[0])
  for (const j of [a, b])
    for (const leg of [j.legN, j.legF])
      expect(Math.min(leg.heel[1], leg.ball[1]), 'a foot on the floor').toBeLessThan(1)
})
