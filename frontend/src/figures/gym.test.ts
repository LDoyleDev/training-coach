import { expect, test } from 'vitest'
import { blend, dist, solve, type Joints, type Vec } from './body'
import { solveFront } from './front'
import { GYM } from './gym'
import { perspectiveShapes } from './perspective'
import { FIGURES } from './poses'
import { moving, shapes } from './shapes'
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

/** The point on the bench's back pad ``s`` cm from its hinge, and the pad's own direction. */
const pad = (slug: string, s: number) => {
  const { x, top, angle } = GYM[slug].props!.incline!
  const a = (angle * Math.PI) / 180
  return [x + s * Math.cos(a), top + s * Math.sin(a)] as const
}

test('a bench press lies on the bench, pressing from the chest to straight up', () => {
  for (const slug of ['db-bench-press', 'incline-db-press']) {
    const [up, down] = [solve(GYM[slug].start), solve(GYM[slug].end)]
    for (const j of along(slug)) {
      // the back on the pad: the shoulders about 12 cm (the trunk's half depth) off its surface
      const surface = pad(slug, dist(j.shoulder, [GYM[slug].props!.incline!.x, 44]))
      expect(dist(j.shoulder, surface), slug).toBeLessThan(16)
      expect(j.legN.heel[1], `${slug}: feet flat on the floor`).toBeLessThan(2)
    }
    expect(fist(up)[1] - up.shoulder[1], `${slug}: arms straight up`).toBeGreaterThan(55)
    expect(Math.abs(fist(up)[0] - up.shoulder[0]), `${slug}: over the chest`).toBeLessThan(8)
    expect(fist(down)[1] - down.shoulder[1], `${slug}: lowered to the chest`).toBeLessThan(20)
    expect(down.armN.elbow[1], `${slug}: elbows below the chest`).toBeLessThan(down.shoulder[1])
  }
})

test('an overhead press sits upright and presses from the shoulders to straight arms', () => {
  const [low, high] = [solve(GYM['db-overhead-press'].start), solve(GYM['db-overhead-press'].end)]
  expect(Math.abs(fist(low)[1] - low.shoulder[1]), 'at shoulder height').toBeLessThan(15)
  expect(fist(high)[1] - high.shoulder[1], 'overhead').toBeGreaterThan(55)
  expect(high.head.c[1]).toBeLessThan(fist(high)[1])
})

test('curls keep the elbows still and bring the weight up', () => {
  for (const slug of ['incline-db-curl', 'hammer-curl']) {
    const [low, high] = [solve(GYM[slug].start), solve(GYM[slug].end)]
    near(low.armN.elbow, high.armN.elbow) // the elbow doesn't move
    expect(low.armN.wrist[1], `${slug}: arm long`).toBeLessThan(low.armN.elbow[1] - 25)
    expect(high.armN.wrist[1], `${slug}: curled`).toBeGreaterThan(high.armN.elbow[1] + 20)
  }
  const incline = solve(GYM['incline-db-curl'].start)
  expect(
    Math.abs(incline.armN.wrist[0] - incline.shoulder[0]),
    'hanging straight down',
  ).toBeLessThan(1)
})

test('a dumbbell is a disc end on, or a handle with two heads along the picture', () => {
  const kinds = (slug: string) => {
    const { start, props, order } = GYM[slug]
    return shapes(start, props, order).filter((s) => 'tone' in s && s.tone === 'bell')
  }
  expect(kinds('db-bench-press').filter((s) => s.kind === 'ball')).toHaveLength(2) // one a hand
  expect(kinds('hammer-curl').filter((s) => s.kind === 'path')).toHaveLength(6)
})

test('a wrist curl moves only the hands, forearms on the thighs', () => {
  const [low, high] = [solve(GYM['wrist-curl'].start), solve(GYM['wrist-curl'].end)]
  near(low.armN.elbow, high.armN.elbow)
  near(low.armN.wrist, high.armN.wrist)
  expect(Math.abs(low.armN.wrist[1] - low.legN.knee[1]), 'forearm on the thigh').toBeLessThan(26)
  expect(low.armN.tip[1], 'wrist bent down').toBeLessThan(low.armN.wrist[1] - 5)
  expect(high.armN.tip[1], 'curled up').toBeGreaterThan(high.armN.wrist[1] + 3)
})

test('a chest-supported row keeps the chest on the pad and pulls to the ribs', () => {
  for (const j of along('chest-supported-row')) {
    near(j.hip, [13, 74])
    near(j.legN.ankle, [-20, 7])
  }
  const [long, pulled] = [
    solve(GYM['chest-supported-row'].start),
    solve(GYM['chest-supported-row'].end),
  ]
  expect(dist(long.armN.wrist, long.shoulder), 'arms long').toBeGreaterThan(54)
  expect(dist(pulled.armN.wrist, pulled.waist), 'to the lower ribs').toBeLessThan(25)
  expect(pulled.armN.elbow[1], 'elbow above the back').toBeGreaterThan(pulled.shoulder[1] - 15)
})

/** The middle of the pad of ``slug``'s machine that moves with the body, at its start or end. */
const movingPad = (slug: string, t: 0 | 1) => {
  const f = GYM[slug]
  const [a, b, c, d] = moving(solve(t ? f.end : f.start), f.props!.machine!.moves!.on)
  return [(a + c) / 2, (b + d) / 2] as const
}

test('a machine draws its moving pad, and its lever or carriage', () => {
  for (const slug of ['leg-press', 'leg-extension', 'standing-calf-raise']) {
    const f = GYM[slug]
    const tubes = shapes(f.start, f.props, f.order).filter(
      (s) => s.kind === 'path' && (s.tone === 'prop' || s.tone === 'bell'),
    )
    expect(tubes.length, slug).toBeGreaterThan(f.props!.machine!.frame!.length + 1)
  }
})

test('a leg press bends the knees well with the back still on the pad and the sled under the feet', () => {
  const [long, bent] = [solve(GYM['leg-press'].start), solve(GYM['leg-press'].end)]
  expect(angleAt(long.hip, long.legN.knee, long.legN.ankle), 'nearly straight').toBeGreaterThan(150)
  expect(angleAt(bent.hip, bent.legN.knee, bent.legN.ankle), 'well bent').toBeLessThan(80)
  near(long.hip, bent.hip)
  for (const t of [0, 1] as const) {
    const j = t ? bent : long
    expect(dist(movingPad('leg-press', t), j.legN.ball), 'the plate under the feet').toBeLessThan(
      15,
    )
  }
  // the sled runs on its 45° rails
  const move = [bent.legN.ankle[0] - long.legN.ankle[0], bent.legN.ankle[1] - long.legN.ankle[1]]
  expect(Math.abs(move[0] - move[1])).toBeLessThan(0.5)
})

test('a leg extension straightens the knee against a roller on the shins; a leg curl bends it', () => {
  const ext = [solve(GYM['leg-extension'].start), solve(GYM['leg-extension'].end)]
  const curl = [solve(GYM['seated-leg-curl'].start), solve(GYM['seated-leg-curl'].end)]
  expect(angleAt(ext[0].hip, ext[0].legN.knee, ext[0].legN.ankle), 'bent').toBeLessThan(100)
  expect(angleAt(ext[1].hip, ext[1].legN.knee, ext[1].legN.ankle), 'straight').toBeGreaterThan(165)
  expect(angleAt(curl[0].hip, curl[0].legN.knee, curl[0].legN.ankle), 'straight').toBeGreaterThan(
    165,
  )
  expect(
    angleAt(curl[1].hip, curl[1].legN.knee, curl[1].legN.ankle),
    'under the seat',
  ).toBeLessThan(90)
  for (const t of [0, 1] as const) {
    const [e, c] = [ext[t], curl[t]]
    const front = movingPad('leg-extension', t)
    const back = movingPad('seated-leg-curl', t)
    expect(dist(front, e.legN.ankle), 'the roller just above the ankle').toBeLessThan(16)
    expect(dist(back, c.legN.ankle)).toBeLessThan(16)
    // in front of the shin for the extension, behind it for the curl
    const side = (p: Vec, j: Joints) =>
      (j.legN.knee[0] - j.legN.ankle[0]) * (p[1] - j.legN.ankle[1]) -
      (j.legN.knee[1] - j.legN.ankle[1]) * (p[0] - j.legN.ankle[0])
    expect(side(front, e)).toBeLessThan(0)
    expect(side(back, c)).toBeGreaterThan(0)
  }
})

test('calf raises rise from the balls of the feet on the edge, under the pads', () => {
  for (const slug of ['standing-calf-raise', 'seated-calf-raise']) {
    const { top, x0 } = GYM[slug].props!.step!
    const [low, high] = [solve(GYM[slug].start), solve(GYM[slug].end)]
    for (const j of [low, high]) near(j.legN.ball, [x0 + 1, top], 0.2)
    expect(low.legN.heel[1], `${slug}: heel below the edge`).toBeLessThan(top - 5)
    expect(high.legN.heel[1], `${slug}: up high`).toBeGreaterThan(top + 10)
    for (const t of [0, 1] as const) {
      const j = t ? high : low
      const pad = movingPad(slug, t)
      const on = slug === 'standing-calf-raise' ? j.shoulder : j.legN.knee
      expect(dist(pad, on), `${slug}: the pad on the shoulders or the knees`).toBeLessThan(18)
      expect(pad[1], 'on top').toBeGreaterThan(on[1])
    }
  }
})

test('a cable runs from its pulley to the hands, and the hand holds its grip', () => {
  for (const slug of ['lat-pulldown', 'overhead-cable-extension', 'cable-crunch', 'pallof-press']) {
    const f = GYM[slug]
    for (const pose of [f.start, f.end]) {
      const drawn = shapes(pose, f.props, f.order)
      const pulley = drawn.find((s) => s.kind === 'ball' && s.r === 4.5)
      expect(pulley?.kind === 'ball' && pulley.c, slug).toEqual(
        [...f.props!.cable!.pulley].map((v, i) => (i ? -v : v)),
      )
      // the cable ends at the near fist: it's the thinnest path, just before the grip
      const cable = drawn.findIndex((s) => s.kind === 'path' && s.d.includes('A 1.1 1.1'))
      expect(cable, slug).toBeGreaterThan(-1)
    }
  }
})

test('a lat pulldown pulls the bar from overhead to the upper chest, the cable straight down', () => {
  const { pulley } = GYM['lat-pulldown'].props!.cable!
  const [up, down] = [solve(GYM['lat-pulldown'].start), solve(GYM['lat-pulldown'].end)]
  expect(fist(up)[1], 'arms up').toBeGreaterThan(up.head.c[1] + 25)
  expect(fist(down)[1], 'to the upper chest').toBeLessThan(down.neckBase[1])
  expect(fist(down)[1]).toBeGreaterThan(down.midChest[1])
  expect(down.armN.elbow[1], 'elbows down').toBeLessThan(down.shoulder[1] - 15)
  for (const j of [up, down])
    expect(Math.abs(fist(j)[0] - pulley[0]), 'under the pulley').toBeLessThan(8)
})

test('an overhead extension bends and straightens the elbows above the shoulders', () => {
  const [bent, straight] = [
    solve(GYM['overhead-cable-extension'].start),
    solve(GYM['overhead-cable-extension'].end),
  ]
  expect(bent.armN.elbow[1], 'elbows by the ears').toBeGreaterThan(bent.shoulder[1] + 20)
  expect(bent.armN.wrist[0], 'hands behind the head').toBeLessThan(bent.head.c[0] - 15)
  expect(angleAt(straight.shoulder, straight.armN.elbow, straight.armN.wrist)).toBeGreaterThan(170)
  expect(straight.armN.wrist[1], 'forward and up').toBeGreaterThan(straight.shoulder[1])
})

test('a cable crunch curls the trunk with the hips still and the rope by the head', () => {
  for (const j of along('cable-crunch')) {
    near(j.hip, [0, 49.4])
    expect(dist(j.armN.wrist, j.head.c), 'rope beside the head').toBeLessThan(12)
    expect(j.legN.knee[1], 'knees on the mat').toBeLessThan(7)
  }
  const [tall, curled] = [solve(GYM['cable-crunch'].start), solve(GYM['cable-crunch'].end)]
  expect(curled.head.c[1], 'ribs towards the hips').toBeLessThan(tall.head.c[1] - 40)
  expect(GYM['cable-crunch'].end.spine, 'back rounded').toBeGreaterThan(30)
})

test('a Pallof press pushes the handle straight out from the chest', () => {
  const [chest, out] = [solve(GYM['pallof-press'].start), solve(GYM['pallof-press'].end)]
  expect(dist(fist(chest), chest.midChest), 'at the chest').toBeLessThan(28)
  expect(angleAt(out.shoulder, out.armN.elbow, out.armN.wrist), 'arms straight').toBeGreaterThan(
    165,
  )
  expect(Math.abs(fist(out)[1] - fist(chest)[1]), 'straight out').toBeLessThan(12)
})

/** The front view of ``slug`` at its start and end. */
const facing = (slug: string) => {
  const front = GYM[slug].front!
  return [solveFront(front.start), solveFront(front.end)]
}

test('sideways cable moves are seen from the front, standing, with a cable to each working hand', () => {
  for (const slug of ['cable-lateral-raise', 'chest-fly']) {
    const front = GYM[slug].front!
    expect(front.standing, slug).toBe(true)
    const bare = perspectiveShapes(front.start, front.camera, undefined, { standing: true })
    const drawn = perspectiveShapes(front.start, front.camera, undefined, front)
    // each cable adds its column, stack, pulley, cable and handle
    expect(drawn.length - bare.length, slug).toBeGreaterThanOrEqual(front.cables!.length * 5)
  }
  const [low, high] = facing('cable-lateral-raise')
  expect(low.armL.end[1], 'the hand by the thigh').toBeLessThan(low.hip[1])
  expect(Math.abs(high.armL.end[1] - high.armL.root[1]), 'to shoulder height').toBeLessThan(8)
  expect(high.armL.end[0] - high.armL.root[0], 'out to the side').toBeGreaterThan(45)
  near(low.armR.end, high.armR.end) // the other hand stays on the hip
})

test('a fly brings the hands together in front; a reverse fly opens them wide', () => {
  const [wide, hug] = facing('chest-fly')
  const [hands, open] = facing('reverse-pec-deck')
  for (const j of [wide, open]) {
    expect(j.armL.end[0] - j.armR.end[0], 'arms wide').toBeGreaterThan(120)
    expect(j.armL.z[1], 'in line with the body').toBeLessThan(5)
  }
  for (const j of [hug, hands]) {
    expect(j.armL.end[0] - j.armR.end[0], 'hands together').toBeLessThan(15)
    expect(j.armL.z[1], 'out in front').toBeGreaterThan(40)
  }
  expect(Math.abs(hands.armL.end[1] - hands.armL.root[1]), 'at shoulder height').toBeLessThan(5)
})

test('a reverse pec deck is a machine: seated, chest on the pad, a lever to each hand', () => {
  const f = GYM['reverse-pec-deck']
  const { machine } = f.props!
  const [seat, chestPad] = machine!.pads!
  for (const j of along('reverse-pec-deck')) {
    expect(j.hip[1] - seat[1], 'sat on the seat').toBeLessThan(16)
    expect(chestPad[0] - j.midChest[0] - 13.5, 'chest on the pad').toBeLessThan(5)
    expect(j.midChest[1], 'the pad at the chest').toBeGreaterThan(chestPad[1])
  }
  // Side on, the handle is in the near fist; from the front, each lever keeps its length.
  for (const t of [0, 1] as const)
    near(movingPad('reverse-pec-deck', t), fist(solve(t ? f.end : f.start)))
  const { front } = f
  for (const { pivot, hand } of front!.machine!.levers!) {
    const reach = facing('reverse-pec-deck').map((j) => {
      const arm = hand === 'L' ? j.armL : j.armR
      return Math.hypot(arm.end[0] - pivot[0], arm.end[1] - pivot[1], arm.z[1] - pivot[2])
    })
    expect(Math.abs(reach[0] - reach[1]), 'a rigid lever').toBeLessThan(6)
  }
  const bare = perspectiveShapes(front!.start, front!.camera, undefined, { standing: true })
  const drawn = perspectiveShapes(front!.start, front!.camera, undefined, front)
  expect(drawn.length - bare.length, 'frame, pads, levers and handles').toBeGreaterThan(12)
})
