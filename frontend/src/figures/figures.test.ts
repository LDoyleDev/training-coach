import { expect, test } from 'vitest'
import { BODY, blend, dist, progress, solve, type Pose } from './body'
import { FIGURES } from './poses'
import { capsule, shapes } from './shapes'

/** Every drawn point of ``pose``: the joints, the hands' and feet's ends, the head. */
function points(j: ReturnType<typeof solve>) {
  const out = [j.hip, j.waist, j.midChest, j.neckBase, j.shoulder, j.neckTop, j.head.c]
  for (const a of [j.armN, j.armF]) out.push(a.shoulder, a.elbow, a.wrist, a.tip)
  for (const l of [j.legN, j.legF]) out.push(l.knee, l.ankle, l.heel, l.ball, l.tip, l.instep)
  return out
}

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

test('every figure is a number all the way through, inside its picture, with two captions', () => {
  for (const [slug, figure] of Object.entries(FIGURES)) {
    expect(
      figure.frames.every((text) => text.length > 0),
      slug,
    ).toBe(true)
    const [x0, x1, , y1] = figure.view
    for (const t of STEPS) {
      const j = solve(blend(figure.start, figure.end, t))
      for (const p of points(j)) {
        expect(Number.isFinite(p[0]) && Number.isFinite(p[1]), `${slug} at ${t}`).toBe(true)
        expect(p[0], `${slug} at ${t}`).toBeGreaterThan(x0)
        expect(p[0], `${slug} at ${t}`).toBeLessThan(x1)
        expect(p[1], `${slug} at ${t}`).toBeLessThan(y1)
      }
      expect(j.head.c[1] + 11.5, `${slug}'s head at ${t}`).toBeLessThan(y1)
      for (const shape of shapes(blend(figure.start, figure.end, t), figure.props))
        expect(JSON.stringify(shape), slug).not.toMatch(/NaN|null/)
    }
  }
})

test('an arm drawn turned towards you never looks longer than it is', () => {
  for (const [slug, figure] of Object.entries(FIGURES))
    for (const t of STEPS) {
      const j = solve(blend(figure.start, figure.end, t))
      for (const side of ['armN', 'armF'] as const) {
        if (!figure.start[side].mid) continue
        expect(dist(j[side].shoulder, j[side].elbow), slug).toBeLessThan(BODY.upperArm + 0.05)
        expect(dist(j[side].elbow, j[side].wrist), slug).toBeLessThan(BODY.forearm + 0.05)
      }
    }
})

test('hands stay on the bar, the seats, the bench or the floor all the way through', () => {
  const grip = (slug: string, side: 'armN' | 'armF', at: readonly number[]) => {
    for (const t of STEPS)
      near(solve(blend(FIGURES[slug].start, FIGURES[slug].end, t))[side].wrist, at)
  }
  for (const slug of ['pull-up', 'chin-up']) {
    const bar = FIGURES[slug].props!.bar!
    grip(slug, 'armN', [bar[0], bar[1] - 4.5]) // the hand wraps the bar
    grip(slug, 'armF', [bar[0], bar[1] - 4.5])
    const top = solve(FIGURES[slug].end)
    expect(top.head.c[1] - 8, `${slug}: chin over the bar`).toBeGreaterThan(bar[1])
    expect(top.head.c[0] + 11.5, `${slug}: face behind the bar`).toBeLessThan(bar[0] - 3)
  }
  grip('dip', 'armN', [-21, 48.4]) // on the seat's front edge
  grip('pike-push-up', 'armN', [60, 3])
  grip('diamond-push-up', 'armN', [110.9, 3])
  grip('kb-row', 'armF', [58, 52.9]) // the supporting hand on the bench
  const { seat } = FIGURES.dip.props!.chair!
  const bottom = solve(FIGURES.dip.end)
  expect(Math.abs(bottom.armN.elbow[1] - bottom.shoulder[1]), 'dip: upper arms level').toBeLessThan(
    2,
  )
  expect(bottom.armN.wrist[1]).toBeGreaterThan(seat)
})

test('a chin-up keeps the elbows in front, a pull-up takes them out to the sides', () => {
  const chin = solve(FIGURES['chin-up'].end)
  const pull = solve(FIGURES['pull-up'].end)
  expect(chin.armN.elbow[0] - chin.shoulder[0]).toBeGreaterThan(15)
  expect(Math.abs(pull.armN.elbow[0] - pull.shoulder[0])).toBeLessThan(5)
})

test('the row keeps a knee and a hand on the bench and the back flat', () => {
  const row = FIGURES['kb-row']
  const { top } = row.props!.bench!
  for (const t of STEPS) {
    const j = solve(blend(row.start, row.end, t))
    expect(j.legF.knee[1] - 5.4, 'the knee rests on the bench').toBeGreaterThan(top - 0.5)
    expect(j.legF.knee[1] - 5.4).toBeLessThan(top + 1)
    expect(j.shoulder[1] - j.hip[1], 'back about level').toBeLessThan(15)
  }
  // The bell hangs on the near side of the bench, below its top, until it's pulled up.
  const hanging = shapes(row.start, row.props, row.order)
    .filter((s) => s.kind === 'ball')
    .at(-1)!
  expect(hanging.kind === 'ball' && -hanging.c[1] + hanging.r).toBeLessThan(top - 5)
  const pulled = solve(row.end)
  expect(pulled.armN.elbow[1], 'elbow above the back').toBeGreaterThan(pulled.shoulder[1])
  expect(dist(pulled.armN.wrist, pulled.hip)).toBeLessThan(20) // the bell at the hip
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
  near(j.armN.elbow, [j.shoulder[0] + 8, j.shoulder[1] + 28.9]) // the elbow as given
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

test('a movement ends exactly on its end pose, and starts on its start pose', () => {
  for (const [slug, figure] of Object.entries(FIGURES)) {
    expect(solve(blend(figure.start, figure.end, 1)), slug).toEqual(solve(figure.end))
    expect(solve(blend(figure.start, figure.end, 0)), slug).toEqual(solve(figure.start))
  }
})

test('blending moves numbers and keeps everything else from the start', () => {
  const a = { lean: 0, hip: [0, 10], from: 'waist', only: 1 }
  const b = { lean: 10, hip: [10, 20], from: 'head' }
  expect(blend(a, b as unknown as typeof a, 0.5)).toEqual({
    lean: 5,
    hip: [5, 15],
    from: 'waist',
    only: 0.5, // a number one pose leaves out counts as 0
  })
  expect(blend({ lean: 0 }, { lean: 10, spine: 8 } as { lean: number }, 0.5)).toEqual({
    lean: 5,
    spine: 4,
  })
  expect(blend({ at: undefined }, { at: 'waist' } as { at?: string }, 0.2)).toEqual({ at: 'waist' })
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
  expect(kinds('kb-row').slice(0, 3)).toEqual(['pathfar', 'pathfar', 'pathfar']) // bench, behind
  const bar = kinds('pull-up')
  expect(bar.at(-1)).toBe('ballbell') // the bar's end, in front of the hands
  expect(bar.slice(0, 3)).toEqual(['pathprop', 'pathbell', 'pathbell']) // wall and bracket
})

test('a one-arm kettlebell hangs straight down from the near hand', () => {
  const row = FIGURES['kb-row']
  for (const pose of [row.start, row.end]) {
    const wrist = solve(pose).armN.wrist
    const ring = shapes(pose, row.props, row.order).find((s) => s.kind === 'ring')!
    expect(ring.kind === 'ring' && ring.c[0]).toBeCloseTo(wrist[0], 5) // under the hand
    expect(ring.kind === 'ring' && -ring.c[1]).toBeCloseTo(wrist[1] - 3.5, 5)
  }
})

test('a hand turned towards you is drawn shorter', () => {
  const j = solve(FIGURES['diamond-push-up'].start)
  expect(dist(j.armN.wrist, j.armN.tip)).toBeCloseTo(BODY.hand / 2, 5)
})
