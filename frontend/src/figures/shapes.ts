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
  | { kind: 'floor'; d: string } // a mat on the floor, seen in perspective

export type Part = 'armN' | 'armF' | 'legN' | 'legF' | 'torso' | 'head' | 'bell'

export interface Props {
  mat?: readonly [number, number] // from x to x, on the floor
  /** A chair, its back at ``x0``; ``beside`` is one each side of you, seen as one chair in
   * front of the figure, as the near one hides the far one. */
  chair?: { x0: number; x1: number; seat: number; beside?: boolean }
  /** A bench or a bed; ``behind`` puts it on the far side of the figure, in the far tone, so
   * the near leg and arm read as in front of it. */
  bench?: { x0: number; x1: number; top: number; behind?: boolean }
  /** A sofa seen from its end, its back at ``x0`` and its front at ``x1``: on short legs, so feet
   * can hook under its frame, with a seat cushion, a back and a rolled arm. */
  sofa?: { x0: number; x1: number }
  bar?: Vec // a pull-up bar seen end on: its centre, on a bracket from the wall in front
  /** A kettlebell in both hands, hanging along the forearms; 'near' hangs it straight down
   * from the near hand, as in a one-arm row; 'hammer' holds it there by the handle stood
   * upright; 'sides' hangs one from each hand, the near one heavier (a suitcase hold);
   * 'goblet' holds it by the horns at the chest, the bell under the hands; 'one' swings it
   * along the near forearm alone (a one-arm swing); 'toes' rests it on the near foot. */
  bell?: boolean | 'near' | 'hammer' | 'sides' | 'goblet' | 'one' | 'toes'
  /** A weighted vest or backpack, packed high on the upper back. */
  load?: boolean
  /** A shopping bag: hanging by its handles from the near hand ('near'), or hugged to the chest
   * in both arms ('chest'). Drawn where the order puts 'bell'. */
  bag?: 'near' | 'chest'
  /** Dip bars seen along their length, their top ``top`` cm off the floor, centred on ``x``. */
  bars?: { x: number; top: number }
  /** A step or a box, its top ``top`` cm off the floor. */
  step?: { x0: number; x1: number; top: number }
  /** A wall from x to x, from the floor to ``top``: behind your back or under a hand. */
  wall?: { x0: number; x1: number; top: number }
  /** Stairs rising away from you, the bottom stair's front at ``x``, each ``rise`` cm high and
   * ``STAIR.run`` deep; ``rail`` adds the banister beside them, behind you, from a newel post at
   * the bottom stair, ``STAIR.rail`` cm above the stairs' edges. */
  stair?: { x: number; rise: number; rail?: boolean }
  /** A kitchen counter beside you, on the far side, from x to x: its cupboard behind your legs and
   * its worktop ``WORKTOP`` cm up, so the far hand can rest on it or wait just above it. */
  worktop?: readonly [number, number]
  /** A towel under the near heel, sliding with it. */
  towel?: boolean
  /** A barbell seen end on, in the near fist: a plate behind the figure, the bar's end in front
   * of it. 'plate' is one plate held in the fist, drawn where the order puts 'bell'. */
  barbell?: true | 'plate'
  /** A squat rack's two uprights behind the figure, at x0 and x1, its safety bars ``pins`` up. */
  rack?: { x0: number; x1: number; pins: number }
  /** A gym bench whose back tilts, hinged at ``x``, the seat's top ``top`` cm up. The back pad
   * runs from the hinge at ``angle`` (180 flat behind you, 150 a 30° incline, 95 upright, 45
   * rising in front, to lie on chest down) and the seat the other way. */
  incline?: { x: number; top: number; angle: number }
  /** A dumbbell in each hand: the handle across the body, seen end on, or along the picture,
   * square to the forearm (palms facing each other). */
  dumbbells?: 'across' | 'along'
  /** A cable column (``Cable``). */
  cable?: Cable
  /** A gym machine seen side on, fixed in place: steel tubes (``frame``) and pads (``pads``)
   * behind the figure, and pads in front of it (``over``), each from [x, y] to [x, y]. A pad from
   * a point to itself is a roller. ``moves`` is the pad that moves with you, on a lever from
   * ``pivot``: the plate under the soles (a leg press's sled), a roller in front of the shins or
   * behind the calves, a pad on the thighs above the knees, pads on the shoulders, or a handle in
   * the near fist. */
  machine?: {
    frame?: readonly Seg[]
    pads?: readonly Seg[]
    over?: readonly Seg[]
    moves?: Moves
  }
  /** A resistance band (``Band``), drawn where the order puts 'bell'. */
  band?: Band
  /** An armchair seen side on, its back at ``x0`` and its front at ``x1``, the armrests behind
   * the figure (``ARMCHAIR`` gives the heights). */
  armchair?: { x0: number; x1: number }
  /** A small water bottle in each fist, lying square to the forearm, its cap forward. */
  bottles?: boolean
}

/** A resistance band from a fixed anchor at ``from`` to the near fist or the near ankle (a loop
 * round it). It is fixed to the top or the edge of a door seen edge on, its edge at ``from[0]``
 * ('door'), or to a heavy table leg at ``from[0]``, the table running away in front of you, behind
 * the figure ('table'). */
export interface Band {
  from: Vec
  to: 'hands' | 'ankle'
  on: 'door' | 'table'
}

/** A cable column: its upright at ``x`` with the weight stack at its foot, the pulley at
 * ``pulley`` (on an arm from the top when it isn't on the upright), and the cable to the near
 * fist, held by a handle, a rope or a long bar (seen end on). */
export interface Cable {
  x: number
  pulley: Vec
  grip: 'handle' | 'rope' | 'bar'
}

type Moves = { on: 'sole' | 'shin' | 'calf' | 'knee' | 'shoulder' | 'hand'; pivot?: Vec }

type Seg = readonly [number, number, number, number]

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

/** A kettlebell held in both hands, hanging along the forearms, or in the near hand alone
 * ('one'); or in the near hand, hanging straight down: from the bottom of the handle, or held by
 * its upright handle ('hammer'); or by the horns at the chest ('goblet'). */
function bell(j: Joints, hold: true | 'near' | 'hammer' | 'goblet' | 'one'): Shape[] {
  const w: Vec =
    hold === true || hold === 'goblet'
      ? [(j.armN.wrist[0] + j.armF.wrist[0]) / 2, (j.armN.wrist[1] + j.armF.wrist[1]) / 2]
      : j.armN.wrist
  const dir = hold === true || hold === 'one' ? heading(j.armN.elbow, j.armN.wrist) : -90
  // Held by the horns, the handle round the hands and the bell under them, against the chest.
  if (hold === 'goblet')
    return [
      { kind: 'ring', c: svg(w), r: 5, ry: 3, width: 2.2, tone: 'bell' },
      ball(along(w, -90, 9.5), 8.6, 'bell'),
    ]
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

/** An 8 kg bell resting on the near foot's forefoot, its handle up, riding with the toes. */
function onToes(j: Joints): Shape[] {
  const up = heading(j.legN.heel, j.legN.tip) + 90
  const c = along(j.legN.instep, up, 7.4)
  return [
    { kind: 'ring', c: svg(along(c, up, 8.6)), r: 3.6, width: 2.2, tone: 'bell' },
    ball(c, 6.8, 'bell'),
  ]
}

/** A bell hanging straight down from ``wrist``; ``r`` is its size (16 kg is 8.6). */
function hanging(wrist: Vec, r: number): Shape[] {
  return [
    { kind: 'ring', c: svg(along(wrist, -90, 3.5)), r: r * 0.53, width: 2.2, tone: 'bell' },
    ball(along(wrist, -90, 4.4 + r), r, 'bell'),
  ]
}

/** A shopping bag, about 3-5 kg: its handles in the near fist and the bag hanging under them, or
 * held in both arms against the chest, the hands at its top. */
function bag(j: Joints, hold: 'near' | 'chest'): Shape[] {
  const [x, y] =
    hold === 'near'
      ? along(j.armN.wrist, -90, 7)
      : [(j.armN.wrist[0] + j.armF.wrist[0]) / 2, (j.armN.wrist[1] + j.armF.wrist[1]) / 2 + 2]
  const body = polygon([
    [x - 9, y],
    [x + 9, y],
    [x + 11, y - 24],
    [x - 11, y - 24],
  ])
  const shapes: Shape[] = [{ kind: 'path', d: body, tone: 'bell' }]
  if (hold === 'near')
    shapes.unshift({
      kind: 'ring',
      c: svg(along(j.armN.wrist, -90, 3)),
      r: 4,
      ry: 4.5,
      width: 2,
      tone: 'bell',
    })
  return shapes
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

/** A chair seen side on, its back at ``x0``: on the left, or on the right if ``x0 > x1``. */
function chair({ x0, x1, seat }: NonNullable<Props['chair']>): Shape[] {
  const s = Math.sign(x1 - x0) // into the seat from its back
  return [
    rect(x0 + s, 0, x0 + 4 * s, seat - 4),
    rect(x1 - 4 * s, 0, x1 - s, seat - 4),
    rect(x0, seat - 4, x1, seat),
    rect(x0, seat, x0 + 3.5 * s, seat + 44),
    rect(x0 - 0.5 * s, seat + 36, x0 + 4 * s, seat + 46),
  ]
}

/** A staircase's depth per stair and the banister's height above the stairs' edges, in cm. */
export const STAIR = { run: 28, rail: 90 }
/** How high the banister of ``stair`` is ``x`` cm along: it rises with the stairs. */
export const railAt = ({ x: x0, rise }: NonNullable<Props['stair']>, x: number) =>
  rise + STAIR.rail + ((x - x0) * rise) / STAIR.run

/** Three stairs in one outline; the banister's newel post and rail, behind the figure. */
function stair(s: NonNullable<Props['stair']>): Shape[] {
  const { x, rise } = s
  const { run } = STAIR
  const steps: Vec[] = [[x, 0]]
  for (let i = 0; i < 3; i++)
    steps.push([x + i * run, (i + 1) * rise], [x + (i + 1) * run, (i + 1) * rise])
  steps.push([x + 3 * run, 0])
  const out: Shape[] = [{ kind: 'path', d: polygon(steps), tone: 'prop' }]
  if (!s.rail) return out
  const [a, b] = [x + 3, x + 3 * run + 6]
  return [
    rect(x + 1, 0, x + 5, railAt(s, a) + 6),
    limb([a, railAt(s, a)], [b, railAt(s, b)], [2.2, 2.2], 'prop'),
    ...out,
  ]
}

/** A kitchen counter's height, in cm. */
export const WORKTOP = 90
function worktop([x0, x1]: readonly [number, number]): Shape[] {
  return [rect(x0 + 2, 0, x1 - 2, WORKTOP - 4), rect(x0, WORKTOP - 4, x1, WORKTOP)]
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

/** Sofa heights in cm: the frame's underside (feet go under it), the seat's top, the arm's top
 * and the back's. */
export const SOFA = { under: 20, seat: 46, arm: 62, back: 88 }

function sofa({ x0, x1 }: NonNullable<Props['sofa']>): Shape[] {
  const s = Math.sign(x1 - x0) // from the back to the front
  const { under, seat, arm, back } = SOFA
  const roll = (arm - seat) / 2 + 1 // the rolled arm's radius
  return [
    rect(x0 + 3 * s, 0, x0 + 7 * s, under),
    rect(x1 - 7 * s, 0, x1 - 3 * s, under),
    // The arm at the far end, behind the cushion, its roll showing above the seat.
    rect(x0, under, x1 - 2 * s, arm - roll),
    limb([x0 + roll * s, arm - roll], [x1 - roll * s, arm - roll], [roll, roll], 'prop'),
    rect(x0, under, x1, seat - 12),
    limb([x0 + 8 * s, seat - 12], [x0 + 12 * s, back - 8], [8, 8], 'prop'),
    limb([x0 + 23 * s, seat - 6], [x1 - 6 * s, seat - 6], [6, 6], 'prop'),
  ]
}

const tubes = (segs: readonly Seg[] = [], r = 2, tone: Tone = 'bell') =>
  segs.map(([a, b, c, d]) => limb([a, b], [c, d], [r, r], tone))
const PAD = 4.5

/** A gym bench: a padded seat and back on a steel frame, behind the figure. */
function incline({ x, top, angle }: NonNullable<Props['incline']>): Shape[] {
  const s = Math.cos((angle * Math.PI) / 180) <= 0 ? 1 : -1 // the seat's way along x
  const end = along([x, top], angle, 82)
  const strut = along([x, top - 7], angle, 45)
  const foot = Math.min(x + 34 * s, strut[0] - 16 * s)
  const pad = (a: Vec, b: Vec, into: number): Shape =>
    limb(along(a, into, 3.6), along(b, into, 3.6), [3.6, 3.6], 'prop')
  return [
    ...tubes([
      [x, 2, x, top - 6],
      [x + 30 * s, 2, x + 30 * s, top - 6],
      [strut[0] - 12 * s, 2, strut[0], strut[1]],
      [foot, 2, Math.max(x + 34 * s, strut[0] - 16 * s), 2],
    ]),
    pad([x + 42 * s, top], [x, top], -90),
    pad([x, top], end, angle + 90 * s),
  ]
}

/** A dumbbell in the fist of ``arm``. */
function dumbbell(arm: ArmJoints, grip: 'across' | 'along'): Shape[] {
  const c: Vec = [(arm.wrist[0] + arm.tip[0]) / 2, (arm.wrist[1] + arm.tip[1]) / 2]
  if (grip === 'across') return [ball(c, 8, 'bell'), ball(c, 2, 'far')]
  const d = heading(arm.elbow, arm.wrist) + 90
  return [
    limb(along(c, d, 9), along(c, d, -9), [1.6, 1.6], 'bell'),
    limb(along(c, d, 8), along(c, d, 13), [6.5, 6.5], 'bell'),
    limb(along(c, d, -8), along(c, d, -13), [6.5, 6.5], 'bell'),
  ]
}

/** The pad of a machine that moves with the body, as a segment. */
export function moving(j: Joints, on: Moves['on']): Seg {
  const seg = (a: Vec, b: Vec): Seg => [a[0], a[1], b[0], b[1]]
  if (on === 'hand') {
    const [x, y] = fist(j) // an upright handle, through the fist
    return [x, y - 6, x, y + 6]
  }
  const leg = j.legN
  if (on === 'sole') {
    const h = heading(leg.heel, leg.tip)
    return seg(along(along(leg.heel, h, -8), h - 90, 5), along(along(leg.tip, h, 8), h - 90, 5))
  }
  if (on === 'shin' || on === 'calf') {
    const up = heading(leg.ankle, leg.knee)
    const c = along(along(leg.ankle, up, 9), up + (on === 'shin' ? -90 : 90), 9)
    return seg(c, c)
  }
  if (on === 'knee') {
    const back = heading(leg.knee, leg.hip)
    return seg(
      along(along(leg.knee, back, 4), back - 90, 11),
      along(along(leg.knee, back, 18), back - 90, 11),
    )
  }
  const up = heading(j.waist, j.neckBase)
  return seg(inFrame(j.shoulder, up, [-10, 10]), inFrame(j.shoulder, up, [5, 10]))
}

/** A machine's moving pad, and the lever or the sled's carriage it moves on. */
function mover(j: Joints, moves: Moves) {
  const [a, b, c, d] = moving(j, moves.on)
  const mid: Vec = [(a + c) / 2, (b + d) / 2]
  // A sled runs on rails straight back from the soles; anything else swings on a lever.
  const pivot = moves.on === 'sole' ? along(mid, heading([a, b], [c, d]) - 90, 18) : moves.pivot
  if (moves.on === 'hand')
    return {
      pad: tubes([[a, b, c, d]], 1.8),
      lever: pivot
        ? [...tubes([[pivot[0], pivot[1], mid[0], mid[1]]]), ball(pivot, 3.5, 'bell')]
        : [],
    }
  return {
    pad: tubes([[a, b, c, d]], PAD, moves.on === 'sole' ? 'bell' : 'prop'),
    lever: pivot ? tubes([[pivot[0], pivot[1], mid[0], mid[1]]], 3) : [],
  }
}

/** The column, its stack and pulley, behind the figure. */
function column({ x, pulley }: Cable): Shape[] {
  const top = Math.max(pulley[1] + 6, 120)
  const out = [rect(x - 4, 0, x + 4, top, 'bell')]
  for (let y = 4; y < 44; y += 6) out.push(rect(x - 9, y, x + 9, y + 5, 'bell'))
  if (Math.abs(pulley[0] - x) > 6) out.push(...tubes([[x, top - 3, pulley[0], top - 3]], 3))
  return [...out, ball(pulley, 4.5, 'far')]
}

/** The cable from the pulley to the near fist, and what the hand holds. */
function cableTo(j: Joints, { pulley, grip }: Cable): Shape[] {
  const c = fist(j)
  const line = limb(pulley, c, [1.1, 1.1], 'far')
  if (grip === 'bar') return [line, ball(c, 2.4, 'bell')]
  if (grip === 'handle')
    return [line, { kind: 'ring', c: svg(c), r: 3.8, width: 1.6, tone: 'bell' }]
  // A rope: its two ends hang past the fist, away from the pulley.
  const away = heading(pulley, c)
  return [
    line,
    limb(c, along(c, away + 15, 9), [1.6, 1.4], 'bell'),
    limb(c, along(c, away - 15, 9), [1.6, 1.4], 'bell'),
  ]
}

/** A squat rack's uprights and safety bars, behind the figure. */
function rack({ x0, x1, pins }: NonNullable<Props['rack']>): Shape[] {
  return [
    rect(x0, 0, x0 + 5, 200, 'far'),
    rect(x1 - 5, 0, x1, 200, 'far'),
    rect(x0, pins - 3, x1, pins, 'bell'),
  ]
}

/** The middle of the near fist, where a bar or a handle is held. */
const fist = (j: Joints): Vec => [
  (j.armN.wrist[0] + j.armN.tip[0]) / 2,
  (j.armN.wrist[1] + j.armN.tip[1]) / 2,
]

/** A barbell's plate, seen flat on, and its hub; or one smaller plate held on its own. */
function plate(j: Joints, alone: boolean): Shape[] {
  const c = fist(j)
  const r = alone ? 15 : 22.5
  return [
    ball(c, r, 'bell'),
    { kind: 'ring', c: svg(c), r: r * 0.68, width: 1.4, tone: 'far' },
    ball(c, r * 0.2, 'far'),
  ]
}

/** A folded towel on the floor, under the near heel. */
function towel(j: Joints): Shape[] {
  const x = j.legN.heel[0]
  return [rect(x - 10, 0, x + 12, 1.6)]
}

/** A door seen edge on, 200 cm high, or a heavy table running away from its near leg, in the far
 * tone: what a band is fixed to. */
export const DOOR = 200
export const TABLE = 72
function anchor({ from: [x], on }: Band): Shape[] {
  if (on === 'door') return [rect(x, 0, x + 4, DOOR)]
  return [rect(x - 3, 0, x + 3, TABLE - 4, 'far'), rect(x - 5, TABLE - 4, x + 45, TABLE, 'far')]
}

/** The band itself: a dark strip from the anchor to the near fist, or to a loop round the near
 * ankle. */
function band(j: Joints, { from, to }: Band): Shape[] {
  const end = to === 'hands' ? fist(j) : j.legN.ankle
  const strip = limb(from, end, [1.2, 1.2], 'bell')
  if (to === 'hands') return [strip]
  return [strip, { kind: 'ring', c: svg(end), r: 4.4, ry: 2.4, width: 2, tone: 'bell' }]
}

/** Armchair heights in cm: the seat cushion's top, the armrests' top and the back's. */
export const ARMCHAIR = { seat: 45, arm: 62, back: 95 }

/** An armchair side on: short legs, a deep seat cushion, a padded back and the armrest, all
 * behind the figure, so the hands rest on the armrest and the body sits in front of it. */
function armchair({ x0, x1 }: NonNullable<Props['armchair']>): Shape[] {
  const s = Math.sign(x1 - x0)
  const { seat, arm, back } = ARMCHAIR
  return [
    rect(x0 + 2 * s, 0, x0 + 6 * s, 12),
    rect(x1 - 6 * s, 0, x1 - 2 * s, 12),
    limb([x0 + 6 * s, 20], [x0 + 9 * s, back - 7], [7, 7], 'prop'),
    limb([x0 + 6 * s, arm - 4], [x1 - 6 * s, arm - 4], [4, 4], 'prop'),
    rect(x1 - 9 * s, 12, x1 - 2 * s, arm - 4),
    rect(x0, 12, x1, seat - 9),
    limb([x0 + 14 * s, seat - 5], [x1 - 6 * s, seat - 5], [5, 5], 'prop'),
  ]
}

/** A half-litre bottle in the fist of ``arm``, square to the forearm, the cap forward. */
function bottle(arm: ArmJoints): Shape[] {
  const c: Vec = [(arm.wrist[0] + arm.tip[0]) / 2, (arm.wrist[1] + arm.tip[1]) / 2]
  const d = heading(arm.elbow, arm.wrist) - 90 // forward, for a forearm pointing up
  return [
    limb(along(c, d, -8), along(c, d, 4), [3.4, 3.4], 'prop'),
    limb(along(c, d, 4), along(c, d, 8.5), [3.4, 1.5], 'prop'),
    limb(along(c, d, 8.5), along(c, d, 10.5), [1.8, 1.8], 'bell'),
  ]
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
  if (props.chair && !props.chair.beside) out.push(...chair(props.chair))
  if (props.bench) out.push(...bench(props.bench))
  if (props.sofa) out.push(...sofa(props.sofa))
  if (props.armchair) out.push(...armchair(props.armchair))
  if (props.band) out.push(...anchor(props.band))
  if (props.bar) out.push(...bracket(props.bar))
  if (props.rack) out.push(...rack(props.rack))
  if (props.cable) out.push(...column(props.cable))
  if (props.incline) out.push(...incline(props.incline))
  if (props.machine)
    out.push(...tubes(props.machine.frame), ...tubes(props.machine.pads, PAD, 'prop'))
  if (props.bars) out.push(...bars(props.bars))
  if (props.stair) out.push(...stair(props.stair))
  if (props.worktop) out.push(...worktop(props.worktop))
  for (const block of [props.wall, props.step])
    if (block) out.push(rect(block.x0, 0, block.x1, block.top))
  return out
}

/** Everything to draw for ``pose``, back to front. */
export function shapes(pose: Pose, props: Props = {}, order: readonly Part[] = ORDER): Shape[] {
  const j = solve(pose)
  const out = scenery(props)
  const moves = props.machine?.moves && mover(j, props.machine.moves)
  if (moves) out.push(...moves.lever)
  if (props.towel) out.push(...towel(j))
  for (const part of order) {
    if (part === 'bell' && props.band) out.push(...band(j, props.band))
    if (part === 'armF') out.push(...arm(j.armF, 'far'))
    else if (part === 'armN') out.push(...arm(j.armN, 'near'))
    else if (part === 'legF') out.push(...leg(j.legF, 'far'))
    else if (part === 'legN') out.push(...leg(j.legN, 'near'))
    else if (part === 'torso' && props.load) out.push(...pack(j), ...torso(j, 'near'), ...strap(j))
    else if (part === 'torso') out.push(...torso(j, 'near'))
    else if (part === 'head') out.push(...head(j, 'near'))
    else if (props.barbell) out.push(...plate(j, props.barbell === 'plate'))
    else if (props.bag) out.push(...bag(j, props.bag))
    else if (props.cable) out.push(...cableTo(j, props.cable))
    else if (props.bell === 'sides') out.push(...hanging(j.armN.wrist, 8.6))
    else if (props.bell === 'toes') out.push(...onToes(j))
    else if (props.bell) out.push(...bell(j, props.bell))
    if (part === 'armF' && props.dumbbells) out.push(...dumbbell(j.armF, props.dumbbells))
    if (part === 'armN' && props.dumbbells) out.push(...dumbbell(j.armN, props.dumbbells))
    if (part === 'armF' && props.bottles) out.push(...bottle(j.armF))
    if (part === 'armN' && props.bottles) out.push(...bottle(j.armN))
    // The far hand's bell, the lighter one, hangs behind the body.
    if (part === 'armF' && props.bell === 'sides') out.push(...hanging(j.armF.wrist, 6.8))
  }
  if (props.bar) out.push(ball(props.bar, BAR, 'bell'))
  if (props.barbell === true) out.push(ball(fist(j), 2.6, 'bell')) // the bar's end, nearest
  if (props.machine) out.push(...tubes(props.machine.over, PAD, 'prop'))
  if (moves) out.push(...moves.pad)
  if (props.chair?.beside) out.push(...chair(props.chair))
  return out
}
