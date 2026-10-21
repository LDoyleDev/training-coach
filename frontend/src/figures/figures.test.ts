import { expect, test } from 'vitest'
import { BODY, blend, dist, progress, solve, type Pose } from './body'
import { FIGURES } from './poses'
import { capsule, shapes } from './shapes'

const STEPS = [0, 0.25, 0.5, 0.75, 1]
const near = (a: readonly number[], b: readonly number[], within = 0.05) =>
  expect(Math.hypot(a[0] - b[0], a[1] - b[1])).toBeLessThan(within)

test('every figure keeps its limbs their length all the way through', () => {
  for (const [slug, figure] of Object.entries(FIGURES))
    for (const t of STEPS) {
      const j = solve(blend(figure.start, figure.end, t))
      for (const leg of [j.legN, j.legF]) {
        expect(dist(leg.hip, leg.knee), slug).toBeCloseTo(BODY.thigh, 1)
        expect(dist(leg.knee, leg.ankle), slug).toBeCloseTo(BODY.shin, 1)
      }
      for (const side of ['armN', 'armF'] as const) {
        if (figure.start[side].mid) continue // drawn foreshortened on purpose
        expect(dist(j[side].shoulder, j[side].elbow), slug).toBeCloseTo(BODY.upperArm, 1)
        expect(dist(j[side].elbow, j[side].wrist), slug).toBeCloseTo(BODY.forearm, 1)
      }
    }
})

test('no joint of any figure goes through the floor', () => {
  for (const [slug, figure] of Object.entries(FIGURES))
    for (const t of STEPS) {
      const j = solve(blend(figure.start, figure.end, t))
      const points = [j.hip, j.waist, j.midChest, j.shoulder, j.head.c]
      for (const a of [j.armN, j.armF]) points.push(a.elbow, a.wrist, a.tip)
      for (const l of [j.legN, j.legF]) points.push(l.knee, l.ankle, l.heel, l.ball, l.tip)
      for (const p of points) expect(p[1], `${slug} at ${t}`).toBeGreaterThan(-0.5)
    }
})

test('planted hands and feet stay where they are put', () => {
  const bridge = FIGURES['glute-bridge']
  for (const t of STEPS) {
    const j = solve(blend(bridge.start, bridge.end, t))
    near(j.legN.ankle, [42, 7]) // the hips rise; the feet stay
    near(j.legF.ankle, [45, 7])
  }
  const floss = FIGURES['hamstring-floss']
  near(solve(floss.end).legN.ankle, [6, 98])
  near(solve(floss.start).armN.wrist, [4, 40]) // hands behind the thigh
})

test('a hand can be placed on the body, and moves with it', () => {
  const hinge = FIGURES['hip-hinge']
  for (const pose of [hinge.start, hinge.end]) {
    const j = solve(pose)
    expect(dist(j.waist, j.armN.wrist)).toBeCloseTo(Math.hypot(4, 2), 1) // hands on the hips
  }
  const turn = FIGURES['quadruped-t-spine-rotation'].end
  const j = solve(turn)
  expect(dist(j.head.c, j.armN.wrist)).toBeCloseTo(8, 1) // behind the head
  near(j.armN.elbow, [j.shoulder[0] + 8, j.shoulder[1] + 30]) // the elbow as given
})

test('a plank keeps the legs straight along the body line', () => {
  const j = solve(FIGURES['push-up'].start)
  expect(dist(j.legN.ankle, j.hip)).toBeCloseTo(BODY.thigh + BODY.shin, 0)
  expect(j.legN.ball[1]).toBeCloseTo(0, 1) // on the balls of the feet
})

test('toes that would go through the floor bend along it', () => {
  const pose: Pose = {
    hip: [0, 49.4],
    lean: 0,
    legN: { at: [-42.5, 11.6], angle: -100 }, // kneeling, toes tucked
    legF: { at: [44, 7] },
    armN: {},
    armF: {},
  }
  const { legN } = solve(pose)
  expect(legN.tip[1]).toBe(0)
  expect(legN.tip[0]).toBeLessThan(legN.ball[0]) // pointing back, away from the knee
})

test('an arm out of reach points at its target, straight', () => {
  const j = solve({
    hip: [0, 90],
    lean: 0,
    legN: { at: [0, 7] },
    legF: { at: [3, 7] },
    armN: { at: [200, 136] },
    armF: { dir: 0, reach: 0.5 },
  })
  expect(j.armN.wrist[0] - j.shoulder[0]).toBeCloseTo(BODY.upperArm + BODY.forearm, 0)
  expect(j.armF.wrist[0] - j.shoulder[0]).toBeGreaterThan(0)
})

test('blending moves numbers and keeps everything else from the start', () => {
  const a = { lean: 0, hip: [0, 10], from: 'waist', only: 1 }
  const b = { lean: 10, hip: [10, 20], from: 'head' }
  expect(blend(a, b as unknown as typeof a, 0.5)).toEqual({
    lean: 5,
    hip: [5, 15],
    from: 'waist',
    only: 1,
  })
})

test('the movement goes there, holds, comes back and rests', () => {
  const motion = {
    ...FIGURES['cat-cow'],
    tempo: [100, 50, 100, 50] as const,
    ease: 'sine' as const,
  }
  expect(progress(motion, 0)).toBe(0)
  expect(progress(motion, 50)).toBeCloseTo(0.5)
  expect(progress(motion, 120)).toBe(1) // holding at the end
  expect(progress(motion, 200)).toBeCloseTo(0.5)
  expect(progress(motion, 270)).toBe(0) // resting at the start
  expect(progress(motion, 300 + 50)).toBeCloseTo(0.5) // and round again
  const swing = FIGURES['kb-swing']
  expect(progress(swing, swing.tempo[0] / 2)).toBeGreaterThan(0.8) // snaps up
})

test('a limb is a closed rounded outline; one inside its own joint is a circle', () => {
  const limb = capsule([0, 0], [0, 30], 5, 4)
  expect(limb).toMatch(/^M .+ A .+ L .+ A .+ Z$/)
  expect(capsule([0, 0], [0, 0.5], 5, 2)).toMatch(/^M .+ a .+ a .+ Z$/)
})

test('props are drawn with the figure', () => {
  const kinds = (slug: string) => {
    const f = FIGURES[slug]
    return shapes(f.start, f.props, f.order).map((s) => s.kind + ('tone' in s ? s.tone : ''))
  }
  expect(kinds('cat-cow')[0]).toBe('mat')
  expect(kinds('kb-swing')).toContain('ringbell')
  expect(kinds('bulgarian-split-squat').filter((k) => k === 'pathprop')).toHaveLength(5) // the chair
  expect(kinds('y-reach').filter((k) => k.endsWith('far')).length).toBeGreaterThan(0)
})
