/**
 * The mannequin as SVG shapes: rounded, tapered limbs with ball joints and a faceless head, like
 * an artist's wooden figure (ADR-0063). Shapes are in SVG units (cm, y down), so the viewBox is
 * the exercise's view with y flipped.
 */
import {
  along,
  heading,
  inFrame,
  solve,
  type ArmJoints,
  type Joints,
  type LegJoints,
  type Pose,
  type Vec,
} from './body'

export type Tone = 'near' | 'far' | 'prop' | 'bell'

export type Shape =
  | { kind: 'path'; d: string; tone: Tone }
  | { kind: 'ball'; c: Vec; r: number; tone: Tone }
  | { kind: 'ring'; c: Vec; r: number; ry?: number; width: number; tone: Tone }
  | { kind: 'mat'; x: number; y: number; width: number; height: number }

export type Part = 'armN' | 'armF' | 'legN' | 'legF' | 'torso' | 'head' | 'bell'

export interface Props {
  mat?: readonly [number, number] // from x to x, on the floor
  chair?: { x0: number; x1: number; seat: number }
  /** A bench or a bed; ``behind`` puts it on the far side of the figure, in the far tone, so
   * the near leg and arm read as in front of it. */
  bench?: { x0: number; x1: number; top: number; behind?: boolean }
  bar?: Vec // a pull-up bar seen end on: its centre, on a bracket from the wall in front
  /** A kettlebell in both hands, hanging along the forearms; 'near' hangs it straight down
   * from the near hand, as in a one-arm row; 'hammer' holds it there by the handle stood
   * upright; 'sides' hangs one from each hand, the near one heavier (a suitcase hold). */
  bell?: boolean | 'near' | 'hammer' | 'sides'
  /** A weighted vest or backpack, packed high on the upper back. */
  load?: boolean
  /** Dip bars seen along their length, their top ``top`` cm off the floor, centred on ``x``. */
  bars?: { x: number; top: number }
  /** A step or a box, its top ``top`` cm off the floor. */
  step?: { x0: number; x1: number; top: number }
  /** A wall from x to x, from the floor to ``top``: behind your back or under a hand. */
  wall?: { x0: number; x1: number; top: number }
  /** A towel under the near heel, sliding with it. */
  towel?: boolean
}

/** Radii in cm: [at the first joint, at the second]. */
export const SIZE = {
  pelvis: [12.5, 11],
  chestLow: [11, 13.5],
  chestHigh: [13.5, 9],
  neck: [4.6, 4.2],
  head: [9, 11.5],
  upperArm: [5.2, 4],
  forearm: [4, 3],
  hand: [2.9, 2.3],
  thigh: [8.2, 5.6],
  shin: [5.4, 3.8],
  joint: { shoulder: 6.4, elbow: 4.1, wrist: 2.9, hip: 7.6, knee: 5.4, ankle: 3.4 },
} as const

/** World (y up) to SVG (y down). */
export const svg = (p: Vec): Vec => [p[0], -p[1]]
const n = (v: number) => Number(v.toFixed(2))
const pt = (p: Vec) => `${n(p[0])} ${n(p[1])}`

/** A tapered capsule from ``a`` (radius ``ra``) to ``b`` (radius ``rb``), as a path. */
export function capsule(a: Vec, b: Vec, ra: number, rb: number): string {
  const p1 = svg(a)
  const p2 = svg(b)
  const d = Math.hypot(p2[0] - p1[0], p2[1] - p1[1])
  if (d <= Math.abs(ra - rb) + 0.05) {
    const [c, r] = ra >= rb ? [p1, ra] : [p2, rb]
    return `M ${pt([c[0] - r, c[1]])} a ${n(r)} ${n(r)} 0 1 0 ${n(2 * r)} 0 a ${n(r)} ${n(r)} 0 1 0 ${n(-2 * r)} 0 Z`
  }
  const th = Math.atan2(p2[1] - p1[1], p2[0] - p1[0])
  const phi = Math.acos((ra - rb) / d)
  const on = (c: Vec, r: number, angle: number): Vec => [
    c[0] + r * Math.cos(angle),
    c[1] + r * Math.sin(angle),
  ]
  // Around the back of the first end, along a tangent, around the far end, back along the other.
  const big1 = phi < Math.PI / 2 ? 1 : 0
  const big2 = phi > Math.PI / 2 ? 1 : 0
  return [
    `M ${pt(on(p1, ra, th + phi))}`,
    `A ${n(ra)} ${n(ra)} 0 ${big1} 1 ${pt(on(p1, ra, th - phi))}`,
    `L ${pt(on(p2, rb, th - phi))}`,
    `A ${n(rb)} ${n(rb)} 0 ${big2} 1 ${pt(on(p2, rb, th + phi))}`,
    'Z',
  ].join(' ')
}

const polygon = (points: Vec[]) => `M ${points.map((p) => pt(svg(p))).join(' L ')} Z`

export const ball = (c: Vec, r: number, tone: Tone): Shape => ({ kind: 'ball', c: svg(c), r, tone })
export const limb = (a: Vec, b: Vec, [ra, rb]: readonly number[], tone: Tone): Shape => ({
  kind: 'path',
  d: capsule(a, b, ra, rb),
  tone,
})

function arm(j: ArmJoints, tone: Tone): Shape[] {
  return [
    limb(j.shoulder, j.elbow, SIZE.upperArm, tone),
    limb(j.wrist, j.tip, SIZE.hand, tone),
    limb(j.elbow, j.wrist, SIZE.forearm, tone),
    ball(j.wrist, SIZE.joint.wrist, tone),
    ball(j.elbow, SIZE.joint.elbow, tone),
    ball(j.shoulder, SIZE.joint.shoulder, tone),
  ]
}

function leg(j: LegJoints, tone: Tone): Shape[] {
  return [
    limb(j.knee, j.ankle, SIZE.shin, tone),
    { kind: 'path', d: polygon([j.back, j.heel, j.ball, j.tip, j.instep]), tone },
    ball(j.ankle, SIZE.joint.ankle, tone),
    limb(j.hip, j.knee, SIZE.thigh, tone),
    ball(j.knee, SIZE.joint.knee, tone),
  ]
}

/** An oval head turned along the neck, with a small nose so it's clear which way it faces. */
function head(j: Joints, tone: Tone): Shape[] {
  const [rx, ry] = SIZE.head
  const { c, dir } = j.head
  const points = Array.from({ length: 24 }, (_, i) => {
    const a = (i / 24) * 2 * Math.PI
    // across the face (rx) and along the neck (ry)
    return along(along(c, dir - 90, rx * Math.cos(a)), dir, ry * Math.sin(a))
  })
  const nose = along(along(c, dir - 90, rx - 0.6), dir, -1.5)
  return [
    limb(j.neckBase, j.neckTop, SIZE.neck, tone),
    { kind: 'path', d: smooth(points.map(svg)), tone },
    ball(nose, 1.7, tone),
  ]
}

/** A closed curve through ``points`` (Catmull-Rom as cubic Béziers). */
export function smooth(points: Vec[]): string {
  const at = (i: number) => points[(i + points.length) % points.length]
  const parts = [`M ${pt(points[0])}`]
  for (let i = 0; i < points.length; i++) {
    const [p0, p1, p2, p3] = [at(i - 1), at(i), at(i + 1), at(i + 2)]
    const c1: Vec = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]
    const c2: Vec = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]
    parts.push(`C ${pt(c1)} ${pt(c2)} ${pt(p2)}`)
  }
  return parts.join(' ') + ' Z'
}

function torso(j: Joints, tone: Tone): Shape[] {
  return [
    limb(j.hip, j.waist, SIZE.pelvis, tone),
    limb(j.midChest, j.neckBase, SIZE.chestHigh, tone),
    limb(j.waist, j.midChest, SIZE.chestLow, tone),
    ball(j.hip, SIZE.joint.hip, tone),
  ]
}

/** A kettlebell held in both hands, hanging along the forearms, or in the near hand, hanging
 * straight down: from the bottom of the handle, or held by its upright handle ('hammer'). */
function bell(j: Joints, hold: true | 'near' | 'hammer'): Shape[] {
  const w: Vec =
    hold === true
      ? [(j.armN.wrist[0] + j.armF.wrist[0]) / 2, (j.armN.wrist[1] + j.armF.wrist[1]) / 2]
      : j.armN.wrist
  const dir = hold === true ? heading(j.armN.elbow, j.armN.wrist) : -90
  // The handle stands upright round the fist, the bell under it.
  if (hold === 'hammer')
    return [
      { kind: 'ring', c: svg(w), r: 3.4, ry: 7.5, width: 2.2, tone: 'bell' },
      ball(along(w, dir, 16), 8.6, 'bell'),
    ]
  return [
    { kind: 'ring', c: svg(along(w, dir, 3.5)), r: 4.6, width: 2.2, tone: 'bell' },
    ball(along(w, dir, 13), 8.6, 'bell'),
  ]
}

/** A bell hanging straight down from ``wrist``; ``r`` is its size (16 kg is 8.6). */
function hanging(wrist: Vec, r: number): Shape[] {
  return [
    { kind: 'ring', c: svg(along(wrist, -90, 3.5)), r: r * 0.53, width: 2.2, tone: 'bell' },
    ball(along(wrist, -90, 4.4 + r), r, 'bell'),
  ]
}

/** A vest or a backpack high on the upper back, behind the trunk, and a strap over the front. */
function pack(j: Joints): Shape[] {
  const up = heading(j.waist, j.neckBase)
  const at = (back: number, rise: number) => inFrame(j.waist, up, [-back, rise])
  return [{ kind: 'path', d: polygon([at(6, 9), at(21, 11), at(22, 29), at(9, 33)]), tone: 'bell' }]
}
function strap(j: Joints): Shape[] {
  const up = heading(j.waist, j.neckBase)
  return [limb(inFrame(j.waist, up, [-9, 30]), inFrame(j.waist, up, [12, 22]), [1.3, 1.3], 'bell')]
}

const rect = (a: number, b: number, c: number, d: number, tone: Tone = 'prop'): Shape => ({
  kind: 'path',
  d: polygon([
    [a, b],
    [c, b],
    [c, d],
    [a, d],
  ]),
  tone,
})

function chair({ x0, x1, seat }: NonNullable<Props['chair']>): Shape[] {
  return [
    rect(x0 + 1, 0, x0 + 4, seat - 4),
    rect(x1 - 4, 0, x1 - 1, seat - 4),
    rect(x0, seat - 4, x1, seat),
    rect(x0, seat, x0 + 3.5, seat + 44),
    rect(x0 - 0.5, seat + 36, x0 + 4, seat + 46),
  ]
}

/** Dip bars along their length: the bar, and a post at each end, behind the figure. */
function bars({ x, top }: NonNullable<Props['bars']>): Shape[] {
  return [
    rect(x - 34, 0, x - 29, top - 2),
    rect(x + 29, 0, x + 34, top - 2),
    rect(x - 38, top - 4, x + 38, top, 'bell'),
  ]
}

function bench({ x0, x1, top, behind }: NonNullable<Props['bench']>): Shape[] {
  const tone: Tone = behind ? 'far' : 'prop'
  return [
    rect(x0 + 3, 0, x0 + 8, top - 6, tone),
    rect(x1 - 8, 0, x1 - 3, top - 6, tone),
    rect(x0, top - 6, x1, top, tone),
  ]
}

/** A folded towel on the floor, under the near heel. */
function towel(j: Joints): Shape[] {
  const x = j.legN.heel[0]
  return [rect(x - 10, 0, x + 12, 1.6)]
}

/** A bar on a bracket from a wall 40 cm in front, drawn behind the figure; the bar's end goes
 * in front of the hands, as the bar is wider than the grip. */
const BAR = 3
function bracket([x, y]: Vec): Shape[] {
  const wall = x + 40
  return [
    rect(wall, 0, wall + 5, y + 40),
    rect(x, y - 1.6, wall, y + 1.6, 'bell'),
    {
      kind: 'path',
      d: polygon([
        [wall, y - 24],
        [wall, y - 19],
        [x + 18, y - 1],
        [x + 12, y - 1],
      ]),
      tone: 'bell',
    },
  ]
}

export const ORDER: readonly Part[] = ['armF', 'legF', 'torso', 'head', 'legN', 'armN']

/** The props that don't move with the body, back to front. */
export function scenery(props: Props): Shape[] {
  const out: Shape[] = []
  if (props.mat)
    out.push({
      kind: 'mat',
      x: props.mat[0],
      y: -1.2,
      width: props.mat[1] - props.mat[0],
      height: 1.2,
    })
  if (props.chair) out.push(...chair(props.chair))
  if (props.bench) out.push(...bench(props.bench))
  if (props.bar) out.push(...bracket(props.bar))
  if (props.bars) out.push(...bars(props.bars))
  for (const block of [props.wall, props.step])
    if (block) out.push(rect(block.x0, 0, block.x1, block.top))
  return out
}

/** Everything to draw for ``pose``, back to front. */
export function shapes(pose: Pose, props: Props = {}, order: readonly Part[] = ORDER): Shape[] {
  const j = solve(pose)
  const out = scenery(props)
  if (props.towel) out.push(...towel(j))
  for (const part of order) {
    if (part === 'armF') out.push(...arm(j.armF, 'far'))
    else if (part === 'armN') out.push(...arm(j.armN, 'near'))
    else if (part === 'legF') out.push(...leg(j.legF, 'far'))
    else if (part === 'legN') out.push(...leg(j.legN, 'near'))
    else if (part === 'torso' && props.load) out.push(...pack(j), ...torso(j, 'near'), ...strap(j))
    else if (part === 'torso') out.push(...torso(j, 'near'))
    else if (part === 'head') out.push(...head(j, 'near'))
    else if (props.bell === 'sides') out.push(...hanging(j.armN.wrist, 8.6))
    else if (props.bell) out.push(...bell(j, props.bell))
    // The far hand's bell, the lighter one, hangs behind the body.
    if (part === 'armF' && props.bell === 'sides') out.push(...hanging(j.armF.wrist, 6.8))
  }
  if (props.bar) out.push(ball(props.bar, BAR, 'bell'))
  return out
}
