/**
 * The mannequin's body, and how a pose becomes joint positions (ADR-0063).
 *
 * World units are centimetres, y up, the floor at y = 0, the figure facing +x. Angles are
 * degrees: 0 points forward (+x), 90 points up.
 */

export type Vec = readonly [number, number]

export const BODY = {
  pelvis: 18, // hip joint to waist
  chest: 30, // waist to the base of the neck, in two halves so the spine can curve
  shoulderDrop: 4, // the shoulder joint sits this far below the base of the neck
  neck: 9,
  upperArm: 30,
  forearm: 26,
  hand: 8,
  thigh: 44,
  shin: 43,
  ankle: 7, // ankle joint above the sole
  heel: 4, // heel behind the ankle
  ball: 13, // ball of the foot ahead of the ankle
  toe: 5,
}

/** An arm or a leg, placed by where its wrist or ankle goes; the elbow or knee is worked out. */
export interface Limb {
  /** The wrist or ankle: world cm, or an offset [forward, up] from `from` in the trunk's frame. */
  at?: Vec
  from?: 'waist' | 'head'
  /** Arms instead of `at`: a direction from the shoulder and a share of the arm's length. */
  dir?: number
  reach?: number
  /** The elbow or knee as an offset from the shoulder or hip, in place of working it out: the
   * limb can then look shorter, as one turning towards you does. */
  mid?: Vec
  /** Which side of the line the elbow or knee goes: +1 counter-clockwise, -1 clockwise. Legs
   * default to +1 (knees forward), arms to -1 (elbows back). */
  bend?: number
  /** The hand's or foot's own angle. Hands carry on from the forearm, feet lie flat (0). */
  angle?: number
  /** A share of the hand's length, for a hand turned towards you (fingers pointing in). Give it
   * in both poses, as a number one pose leaves out blends from 0. */
  hand?: number
  /** How high the surface under the foot is (a step), for toes that bend along it. */
  floor?: number
}

export interface Pose {
  /** The hip joint, or for a plank the ball of the feet and the body line's angle. */
  hip?: Vec
  plank?: { ball: Vec; angle: number }
  lean: number // the trunk, degrees forward of vertical
  spine?: number // + rounds (cat), - arches (cow)
  neck?: number // + tucks the chin, - looks up
  armN: Limb // near side
  armF: Limb // far side
  legN: Limb
  legF: Limb
}

export interface ArmJoints {
  shoulder: Vec
  elbow: Vec
  wrist: Vec
  tip: Vec
}

export interface LegJoints {
  hip: Vec
  knee: Vec
  ankle: Vec
  heel: Vec
  ball: Vec
  tip: Vec
  instep: Vec
  back: Vec
}

export interface Joints {
  hip: Vec
  waist: Vec
  midChest: Vec
  neckBase: Vec
  shoulder: Vec
  neckTop: Vec
  head: { c: Vec; dir: number }
  armN: ArmJoints
  armF: ArmJoints
  legN: LegJoints
  legF: LegJoints
}

const rad = (d: number) => (d * Math.PI) / 180
const deg = (r: number) => (r * 180) / Math.PI
const unit = (d: number): Vec => [Math.cos(rad(d)), Math.sin(rad(d))]
export const along = (p: Vec, d: number, len: number): Vec => {
  const [ux, uy] = unit(d)
  return [p[0] + ux * len, p[1] + uy * len]
}
export const heading = (a: Vec, b: Vec) => deg(Math.atan2(b[1] - a[1], b[0] - a[0]))
export const dist = (a: Vec, b: Vec) => Math.hypot(b[0] - a[0], b[1] - a[1])
const plus = (a: Vec, b: Vec): Vec => [a[0] + b[0], a[1] + b[1]]

/** Two bones from ``root`` towards ``target``; out of reach, the limb points at it, straight. */
function twoBone(root: Vec, target: Vec, a: number, b: number, bend: number) {
  const d = Math.min(Math.max(dist(root, target), Math.abs(a - b) + 0.01), a + b - 0.01)
  const alpha = deg(Math.acos((a * a + d * d - b * b) / (2 * a * d)))
  const mid = along(root, heading(root, target) + (bend > 0 ? alpha : -alpha), a)
  return { mid, end: along(mid, heading(mid, target), b) }
}

/** A point given as [forward, up] in a frame whose "up" is ``dir``. */
const inFrame = (origin: Vec, dir: number, [forward, up]: Vec): Vec =>
  along(along(origin, dir - 90, forward), dir, up)

/** Blend two poses: numbers are interpolated, a number one pose leaves out counts as 0 (as
 * ``spine`` and ``neck`` do), and anything else comes from ``a``, or ``b`` if ``a`` lacks it. */
export function blend<T>(a: T, b: T, t: number): T {
  if (typeof a === 'number' && typeof b === 'number') return (a + (b - a) * t) as T
  if (Array.isArray(a) && Array.isArray(b)) return a.map((v, i) => blend(v, b[i], t)) as T
  if (a && b && typeof a === 'object') {
    const one = a as Record<string, unknown>
    const other = b as Record<string, unknown>
    const out: Record<string, unknown> = {}
    for (const k of new Set([...Object.keys(one), ...Object.keys(other)])) {
      const [x, y] = [one[k], other[k]]
      if (typeof x === 'number' || typeof y === 'number') out[k] = blend(x ?? 0, y ?? 0, t)
      else out[k] = x !== undefined && y !== undefined ? blend(x, y, t) : (x ?? y)
    }
    return out as T
  }
  return a
}

/** A plank pivots on the balls of the feet: the legs are straight along the body line. */
function fromPlank(pose: Pose): Pose & { hip: Vec } {
  const { ball, angle } = pose.plank!
  const foot = angle - 90 // the foot stays square to the shin
  const [ux, uy] = unit(foot)
  const [nx, ny] = unit(foot - 90)
  const ankle: Vec = [
    ball[0] - BODY.ball * ux - BODY.ankle * nx,
    ball[1] - BODY.ball * uy - BODY.ankle * ny,
  ]
  const hip = along(ankle, angle, BODY.thigh + BODY.shin - 0.1)
  const leg: Limb = { at: ankle, angle: foot }
  return { ...pose, hip, lean: 90 - angle, legN: leg, legF: { ...leg } }
}

/** The foot from its ankle and angle: u along the foot, n towards the sole. Toes that would go
 * through the floor, or the step under them, bend along it. */
function foot(ankle: Vec, angle: number, floor = 0) {
  const u = unit(angle)
  const n = unit(angle - 90)
  const at = (fu: number, fn: number): Vec => [
    ankle[0] + u[0] * fu + n[0] * fn,
    ankle[1] + u[1] * fu + n[1] * fn,
  ]
  const ball = at(BODY.ball, BODY.ankle)
  let tip = at(BODY.ball + BODY.toe, BODY.ankle - 0.5)
  if (tip[1] < floor) {
    const dx = Math.sqrt(Math.max(0, BODY.toe ** 2 - (ball[1] - floor) ** 2))
    tip = [ball[0] + dx * (Math.sign(u[0]) || 1), floor]
  }
  return {
    heel: at(-BODY.heel, BODY.ankle - 1.5),
    ball,
    tip,
    instep: at(BODY.ball - 2, 2.2),
    back: at(-2.5, 0.5),
  }
}

/** Every joint of ``input``. */
export function solve(input: Pose): Joints {
  const pose = input.plank ? fromPlank(input) : { ...input, hip: input.hip ?? ([0, 0] as Vec) }
  const lower = 90 - pose.lean
  const spine = pose.spine ?? 0
  const midDir = lower - spine / 2
  const topDir = midDir - spine / 2
  const neckDir = topDir - (pose.neck ?? 0)
  const hip = pose.hip
  const waist = along(hip, lower, BODY.pelvis)
  const midChest = along(waist, midDir, BODY.chest / 2)
  const neckBase = along(midChest, topDir, BODY.chest / 2)
  const shoulder = along(midChest, topDir, BODY.chest / 2 - BODY.shoulderDrop)
  const neckTop = along(neckBase, neckDir, BODY.neck)
  const head = { c: inFrame(neckTop, neckDir, [2, 9.5]), dir: neckDir }

  const place = (limb: Limb, root: Vec, a: number, b: number, fallback: number) => {
    let target: Vec
    if (limb.at && limb.from === 'waist') target = inFrame(waist, lower, limb.at)
    else if (limb.at && limb.from === 'head') target = inFrame(head.c, topDir, limb.at)
    else if (limb.at) target = limb.at
    else target = along(root, limb.dir ?? -90, (limb.reach ?? 1) * (a + b))
    if (!limb.mid) return twoBone(root, target, a, b, limb.bend ?? fallback)
    return { mid: plus(root, limb.mid), end: target } // drawn as given, foreshortened
  }

  const arm = (limb: Limb): ArmJoints => {
    const { mid, end } = place(limb, shoulder, BODY.upperArm, BODY.forearm, -1)
    return {
      shoulder,
      elbow: mid,
      wrist: end,
      tip: along(end, limb.angle ?? heading(mid, end), BODY.hand * (limb.hand ?? 1)),
    }
  }
  const leg = (limb: Limb): LegJoints => {
    const { mid, end } = place(limb, hip, BODY.thigh, BODY.shin, 1)
    return { hip, knee: mid, ankle: end, ...foot(end, limb.angle ?? 0, limb.floor) }
  }

  return {
    hip,
    waist,
    midChest,
    neckBase,
    shoulder,
    neckTop,
    head,
    armN: arm(pose.armN),
    armF: arm(pose.armF),
    legN: leg(pose.legN),
    legF: leg(pose.legF),
  }
}

export const EASE = {
  inOut: (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2),
  sine: (t: number) => -(Math.cos(Math.PI * t) - 1) / 2,
  out: (t: number) => 1 - (1 - t) ** 3,
}
export type Ease = keyof typeof EASE

/** The movement over time: [to the end, hold there, back to the start, hold there] in ms. */
export interface Motion {
  start: Pose
  end: Pose
  tempo: readonly [number, number, number, number]
  ease?: Ease
  easeGo?: Ease // the way there, when it differs (a swing snaps up and floats down)
}

/** How far between start (0) and end (1) the movement is ``ms`` into its loop. */
export function progress(motion: Motion, ms: number): number {
  const [go, hold, back, rest] = motion.tempo
  const t =
    ((ms % (go + hold + back + rest)) + (go + hold + back + rest)) % (go + hold + back + rest)
  const ease = EASE[motion.ease ?? 'inOut']
  if (t < go) return Math.max(0, EASE[motion.easeGo ?? motion.ease ?? 'inOut'](t / go))
  if (t < go + hold) return 1
  if (t < go + hold + back) return 1 - ease((t - go - hold) / back)
  return 0
}
