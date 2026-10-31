import { expect, test } from 'vitest'
import { BODY, blend, dist, heading, solve, type Joints, type Vec } from './body'
import { ENTRY_UPPER } from './entry-upper'
import { solveFront, type FrontJoints, type FrontPose } from './front'
import { perspectiveShapes } from './perspective'
import { FIGURES, type Figure } from './poses'
import { ARMCHAIR, DOOR, TABLE, shapes, type Shape } from './shapes'
import { figureFor } from './steps'

const ALONG = [0, 0.25, 0.5, 0.75, 1]
const poses = (f: Figure) => ALONG.map((t) => solve(blend(f.start, f.end, t)))
const fronts = (f: Figure) => ALONG.map((t) => solveFront(blend(f.front!.start, f.front!.end, t)))
const fist = (j: Joints): Vec => [
  (j.armN.wrist[0] + j.armN.tip[0]) / 2,
  (j.armN.wrist[1] + j.armN.tip[1]) / 2,
]
/** The points a drawn shape's outline passes through, in world cm (y up). */
const outline = (s: Shape): Vec[] =>
  s.kind === 'path' ? [...s.d.matchAll(/(-?[\d.]+) (-?[\d.]+)/g)].map((m) => [+m[1], -m[2]]) : []
const tones = (drawn: Shape[], tone: string, kind = 'path') =>
  drawn.filter((s) => s.kind === kind && 'tone' in s && s.tone === tone)

test('the entry figures are figures', () => {
  for (const slug of Object.keys(ENTRY_UPPER)) expect(FIGURES[slug], slug).toBe(ENTRY_UPPER[slug])
})

test('an armchair press-up keeps the hands on the armrests and lifts the hips off the seat', () => {
  const press = FIGURES['armchair-press-up']
  const { x0, x1 } = press.props!.armchair!
  for (const j of poses(press)) {
    for (const arm of [j.armN, j.armF]) {
      expect(arm.wrist[1] - ARMCHAIR.arm, 'hands on the armrests').toBeCloseTo(4, 0)
      expect(arm.wrist[0]).toBeGreaterThan(x0)
      expect(arm.wrist[0]).toBeLessThan(x1)
    }
    expect(j.legN.heel[1], 'feet on the floor').toBeLessThan(2)
  }
  const [down, up] = [solve(press.start), solve(press.end)]
  expect(down.hip[1] - ARMCHAIR.seat, 'sitting on the seat').toBeLessThan(12)
  expect(up.hip[1] - down.hip[1], 'hips lifted').toBeGreaterThan(15)
  expect(dist(up.shoulder, up.armN.wrist), 'arms straight').toBeGreaterThan(53)
  expect(dist(down.shoulder, down.armN.wrist), 'arms bent').toBeLessThan(45)
  // Legs, frame, back, armrest, its post, the base and the cushion, behind the figure.
  const drawn = shapes(press.start, press.props, press.order)
  expect(tones(drawn, 'prop')).toHaveLength(7)
  expect(drawn.findIndex((s) => 'tone' in s && s.tone !== 'prop')).toBe(7)
})

/** The band strip runs from ``from`` to ``to``: its outline passes round both. */
function runs(drawn: Shape[], from: Vec, to: Vec, name: string) {
  const strip = tones(drawn, 'bell').find((s) => {
    const ps = outline(s)
    return ps.some((p) => dist(p, from) < 1.5) && ps.some((p) => dist(p, to) < 1.5)
  })
  expect(strip, `${name}: a band from the anchor to the hands`).toBeDefined()
}

const BANDS = ['band-pushdown', 'band-row', 'band-pulldown']

test('a band runs from its door to the hands all the way through', () => {
  for (const slug of BANDS) {
    const figure = FIGURES[slug]
    const band = figure.props!.band!
    expect(band.on, slug).toBe('door')
    expect(figure.order, `${slug} draws the band`).toContain('bell')
    for (const t of ALONG) {
      const pose = blend(figure.start, figure.end, t)
      runs(shapes(pose, figure.props, figure.order), band.from, fist(solve(pose)), slug)
      // The door is in front of you, and the band comes to you from it.
      expect(band.from[0], slug).toBeGreaterThan(fist(solve(pose))[0] + 15)
    }
  }
  // Over the door's top for a pushdown and a pulldown; shut in it at chest height for a row.
  expect(FIGURES['band-pushdown'].props!.band!.from[1]).toBe(DOOR)
  expect(FIGURES['band-pulldown'].props!.band!.from[1]).toBe(DOOR)
  const row = FIGURES['band-row']
  const start = solve(row.start)
  expect(Math.abs(row.props!.band!.from[1] - start.shoulder[1]), 'at chest height').toBeLessThan(5)
  // The door: one slab, behind the figure.
  const door = shapes(row.start, row.props, row.order)
  const plain = shapes(row.start, { chair: row.props!.chair }, row.order)
  expect(tones(door, 'prop').length - tones(plain, 'prop').length).toBe(1)
})

test('a pushdown keeps the elbows at the sides; only the forearms move', () => {
  const push = FIGURES['band-pushdown']
  for (const j of poses(push)) {
    // Within the trunk's depth: the hands move on an arc, so the elbow gives a little mid-way.
    expect(Math.abs(j.armN.elbow[0] - j.shoulder[0]), 'elbows at the sides').toBeLessThan(12)
    expect(j.shoulder[1] - j.armN.elbow[1]).toBeGreaterThan(BODY.upperArm - 4)
    expect(j.legN.heel[1], 'standing').toBeLessThan(2)
  }
  const [up, down] = [solve(push.start), solve(push.end)]
  for (const j of [up, down]) expect(Math.abs(j.armN.elbow[0] - j.shoulder[0])).toBeLessThan(3)
  expect(up.armN.wrist[1], 'hands at chest height').toBeGreaterThan(up.armN.elbow[1] + 10)
  expect(down.armN.wrist[1], 'pushed down').toBeLessThan(down.armN.elbow[1] - 20)
})

test('seated band moves and the press stay on the chair, feet flat', () => {
  for (const slug of [...BANDS.slice(1), 'band-pull-apart', 'seated-press', 'adductor-squeeze']) {
    const { chair } = FIGURES[slug].props!
    for (const j of poses(FIGURES[slug])) {
      expect(j.hip[1] - chair!.seat, `${slug}: on the seat`).toBeGreaterThan(6)
      expect(j.hip[1] - chair!.seat).toBeLessThan(12)
      expect(j.hip[0]).toBeGreaterThan(chair!.x0)
      expect(j.hip[0]).toBeLessThan(chair!.x1)
      for (const leg of [j.legN, j.legF]) expect(leg.heel[1], `${slug}: feet flat`).toBeLessThan(2)
    }
  }
})

test('a row pulls the hands from arms straight to the ribs; a pulldown from overhead', () => {
  const row = FIGURES['band-row']
  const [out, back] = [solve(row.start), solve(row.end)]
  expect(dist(out.shoulder, out.armN.wrist), 'arms straight').toBeGreaterThan(53)
  expect(back.armN.elbow[0], 'elbows behind you').toBeLessThan(back.hip[0])
  expect(back.armN.wrist[1], 'to the ribs').toBeLessThan(back.shoulder[1])
  const pull = FIGURES['band-pulldown']
  const [high, low] = [solve(pull.start), solve(pull.end)]
  expect(high.armN.wrist[1], 'arms up').toBeGreaterThan(high.head.c[1] + 15)
  expect(low.armN.elbow[1], 'elbows down').toBeLessThan(low.shoulder[1] - 15)
})

test('a seated press holds a bottle in each fist, from the shoulders to overhead', () => {
  const press = FIGURES['seated-press']
  const drawn = shapes(press.start, press.props, press.order)
  const plain = shapes(press.start, { chair: press.props!.chair }, press.order)
  expect(drawn.length - plain.length, 'a body, a neck and a cap each').toBe(6)
  const [low, high] = [solve(press.start), solve(press.end)]
  expect(Math.abs(low.armN.wrist[1] - low.shoulder[1]), 'at the shoulders').toBeLessThan(10)
  expect(high.armN.wrist[1], 'overhead').toBeGreaterThan(high.head.c[1] + 15)
  // One arm with 8 kg: the bell under the near fist, the free hand on the thigh.
  const one = figureFor('seated-press', '8 kg, one arm at a time')!
  expect(one.props!.bottles).toBeUndefined()
  for (const t of ALONG) {
    const pose = blend(one.start, one.end, t)
    const j = solve(pose)
    const balls = shapes(pose, one.props, one.order).filter(
      (s) => s.kind === 'ball' && s.tone === 'bell',
    )
    expect(balls).toHaveLength(1)
    const bell = balls[0]
    if (bell.kind !== 'ball') throw new Error('a bell')
    expect(bell.c[0]).toBeCloseTo(j.armN.wrist[0], 5)
    const thigh = j.legF
    const along = (j.armF.wrist[0] - thigh.hip[0]) / (thigh.knee[0] - thigh.hip[0])
    const top = thigh.hip[1] + along * (thigh.knee[1] - thigh.hip[1])
    expect(j.armF.wrist[1] - top, 'the free hand on the thigh').toBeLessThan(10)
    expect(j.armF.wrist[1] - top).toBeGreaterThan(0)
  }
})

/** Every point of a front view's drawing, and its limbs, inside its picture and their length. */
function frontFits(figure: Figure, name: string) {
  const front = figure.front!
  const [x0, x1, y0, y1] = front.view
  for (const t of ALONG) {
    const pose = blend(front.start, front.end, t)
    const j = solveFront(pose)
    const far = (a: Vec, za: number, b: Vec, zb: number) => Math.hypot(dist(a, b), zb - za)
    for (const leg of [j.legL, j.legR]) {
      expect(far(leg.root, 0, leg.mid, leg.z[0]), name).toBeCloseTo(BODY.thigh, 1)
      expect(far(leg.mid, leg.z[0], leg.end, leg.z[1]), name).toBeCloseTo(BODY.shin, 1)
    }
    for (const shape of perspectiveShapes(pose, front.camera, front.seat, front)) {
      expect(JSON.stringify(shape), name).not.toMatch(/NaN|null/)
      if (shape.kind === 'floor') continue
      const points =
        shape.kind === 'ball'
          ? [
              [shape.c[0] - shape.r, -shape.c[1] - shape.r],
              [shape.c[0] + shape.r, -shape.c[1] + shape.r],
            ]
          : outline(shape)
      for (const [x, y] of points) {
        expect(x, name).toBeGreaterThan(x0)
        expect(x, name).toBeLessThan(x1)
        expect(y, name).toBeGreaterThan(y0)
        expect(y, name).toBeLessThan(y1)
      }
    }
  }
}

test('a pull-apart is seen from the front only: the band between the hands, pulled wide', () => {
  const apart = FIGURES['band-pull-apart']
  expect(apart.front!.only).toBe(true)
  const [start, end] = [solveFront(apart.front!.start), solveFront(apart.front!.end)]
  expect(start.armL.z[1], 'arms out in front').toBeGreaterThan(50)
  expect(start.armL.end[0] - start.armR.end[0], 'shoulder-width').toBeLessThan(40)
  expect(end.armL.end[0] - end.armR.end[0], 'out to the sides').toBeGreaterThan(130)
  for (const j of [start, end])
    expect(Math.abs(j.armL.end[1] - j.armL.root[1]), 'at shoulder height').toBeLessThan(10)
  const drawn = perspectiveShapes(
    apart.front!.end,
    apart.front!.camera,
    apart.front!.seat,
    apart.front,
  )
  const bare = perspectiveShapes(apart.front!.end, apart.front!.camera, apart.front!.seat)
  expect(tones(drawn, 'bell').length - tones(bare, 'bell').length, 'the band').toBe(1)
  frontFits(apart, 'band-pull-apart')
})

const gap = (j: FrontJoints) => j.legL.mid[0] - j.legR.mid[0]

test('a pillow squeeze: the knees squeeze in on a pillow, seen from the front', () => {
  const squeeze = FIGURES['adductor-squeeze']
  const { front } = squeeze
  expect(front!.only).toBe(true)
  const [open, shut] = [solveFront(front!.start), solveFront(front!.end)]
  expect(gap(open) - gap(shut), 'knees in').toBeGreaterThan(4)
  for (const j of fronts(squeeze)) {
    expect(j.legL.end[1], 'feet on the floor').toBe(7)
    expect(j.hip[1] - front!.seat!.top, 'on the seat').toBeLessThan(12)
  }
  // The pillow is drawn between the knees, and narrower when squeezed.
  const pillow = (pose: FrontPose) => {
    const drawn = perspectiveShapes(pose, front!.camera, front!.seat, front)
    const bare = perspectiveShapes(pose, front!.camera, front!.seat, { standing: true })
    expect(drawn).toHaveLength(bare.length + 1)
    const xs = drawn
      .filter((s) => !bare.some((b) => JSON.stringify(b) === JSON.stringify(s)))
      .flatMap(outline)
      .map((p) => p[0])
    return Math.max(...xs) - Math.min(...xs)
  }
  expect(pillow(front!.start)).toBeGreaterThan(pillow(front!.end) + 2)
  frontFits(squeeze, 'adductor-squeeze')
})

test('band adduction sweeps the banded leg across in front of the standing one', () => {
  for (const step of [
    'Standing band adduction, light band',
    'Standing band adduction, medium band',
  ]) {
    const adduct = figureFor('adductor-squeeze', step)!
    const front = adduct.front!
    expect(front.only, step).toBe(true)
    expect(front.band).toMatchObject({ to: 'ankleR' })
    for (const j of fronts(adduct)) {
      expect(dist(j.legL.end, [11, 7]), 'the standing foot planted').toBeLessThan(0.01)
      expect(j.armL.end[1] - 90, 'a hand on the counter').toBeCloseTo(2, 0)
      expect(j.armL.end[0], 'on it').toBeGreaterThan(44)
      expect(j.legR.end[1], 'the banded foot off the floor').toBeGreaterThan(7)
      expect(dist(j.legR.root, j.legR.end) ** 2 + j.legR.z[1] ** 2, 'straight').toBeCloseTo(
        87 ** 2,
        0,
      )
    }
    const [out, across] = [solveFront(front.start), solveFront(front.end)]
    expect(out.legR.end[0], 'out to the side').toBeLessThan(-30)
    expect(across.legR.end[0], 'across the other').toBeGreaterThan(across.legL.end[0])
    expect(across.legR.z[1], 'in front of it').toBeGreaterThan(10)
    // The table is on the banded leg's side, the band from its front leg at ankle height.
    const { from } = front.band as { from: readonly number[] }
    expect(from[0] + 4).toBe(front.seat!.x1)
    expect(from[1]).toBeLessThan(12)
    frontFits(adduct, step)
  }
})

test('a standing hamstring curl keeps the knees side by side and the hands on the counter', () => {
  const curl = FIGURES['standing-leg-curl']
  const { top } = curl.props!.wall!
  for (const j of poses(curl)) {
    for (const arm of [j.armN, j.armF]) expect(arm.wrist[1] - top).toBeCloseTo(2, 0)
    expect(dist(j.legF.ankle, [3, 7]), 'the standing foot planted').toBeLessThan(0.01)
    expect(Math.abs(j.legN.knee[0] - j.legF.knee[0]), 'knees side by side').toBeLessThan(8)
  }
  const up = solve(curl.end).legN
  expect(up.ankle[1], 'heel up behind').toBeGreaterThan(50)
  expect(up.ankle[0]).toBeLessThan(up.knee[0] - 30)
  const bend = Math.abs(heading(up.knee, up.hip) - heading(up.knee, up.ankle))
  expect(bend, 'knee bent past square').toBeLessThan(90)
})

test('with a band, the curl pulls against a band from a table leg in front to the ankle', () => {
  for (const step of ['Light band', 'Medium band']) {
    const curl = figureFor('standing-leg-curl', step)!
    const band = curl.props!.band!
    expect(band).toMatchObject({ to: 'ankle', on: 'table' })
    expect(curl.start, step).toBe(FIGURES['standing-leg-curl'].start)
    for (const t of ALONG) {
      const pose = blend(curl.start, curl.end, t)
      const j = solve(pose)
      const drawn = shapes(pose, curl.props, curl.order)
      runs(drawn, band.from, j.legN.ankle, step)
      expect(band.from[0], 'in front of you').toBeGreaterThan(j.legN.ankle[0] + 20)
      expect(
        drawn.filter((s) => s.kind === 'ring'),
        'a loop round the ankle',
      ).toHaveLength(1)
    }
    // The table: a leg and its top, in the far tone, behind the counter.
    const plain = shapes(curl.start, { wall: curl.props!.wall }, curl.order)
    const drawn = shapes(curl.start, curl.props, curl.order)
    expect(tones(drawn, 'far').length - tones(plain, 'far').length).toBe(2)
    const tableTop = Math.max(
      ...tones(drawn, 'far')
        .slice(0, 2)
        .flatMap(outline)
        .map((p) => p[1]),
    )
    expect(tableTop).toBe(TABLE)
  }
})
