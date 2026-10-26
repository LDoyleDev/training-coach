/**
 * The mannequin from the front (ADR-0063, addendum): for a movement that happens side-on to the
 * body, such as a side plank, which the side view draws as if face down. Same units and angles
 * as body.ts. Facing you, the person's left is on your right while they stand upright.
 */
import { BODY, along, heading, inFrame, twoBone, type Vec } from './body'
import { SIZE, ball, limb, scenery, smooth, svg, type Props, type Shape, type Tone } from './shapes'

/** A hand or foot target; the elbow or knee is worked out, unless ``mid`` gives it. */
export interface FrontLimb {
  /** World cm, or with ``from: 'waist'`` an offset [towards the left side, up the trunk]. */
  at: Vec
  from?: 'waist'
  /** The elbow or knee as an offset from the shoulder or hip, for a limb turned towards you. */
  mid?: Vec
  /** Which side of the line the elbow or knee goes: +1 counter-clockwise, -1 clockwise. */
  bend?: number
  /** The hand's or foot's angle; it carries on from the forearm or shin by default. */
  angle?: number
}

export interface FrontPose {
  hip: Vec // midway between the hip joints
  tilt: number // from the hips towards the waist, degrees (90 upright)
  /** The trunk bending sideways at the waist: the chest's tilt less the hips'. */
  bend?: number
  armL: FrontLimb
  armR: FrontLimb
  legL: FrontLimb
  legR: FrontLimb
}

export type FrontPart = 'armL' | 'armR' | 'legL' | 'legR' | 'torso' | 'head'

/** Half the width between the shoulder joints and between the hip joints. */
export const WIDTH = { shoulder: 18, hip: 9 }
const FOOT = 9 // a foot seen from the front, toes towards you

export interface FrontLimbJoints {
  root: Vec
  mid: Vec
  end: Vec
  tip: Vec
}

export interface FrontJoints {
  hip: Vec
  waist: Vec
  shoulders: Vec // midway between the shoulder joints
  neckBase: Vec
  neckTop: Vec
  head: Vec
  armL: FrontLimbJoints
  armR: FrontLimbJoints
  legL: FrontLimbJoints
  legR: FrontLimbJoints
}

/** Every joint of ``pose`` seen from the front. */
export function solveFront(pose: FrontPose): FrontJoints {
  const { hip, tilt } = pose
  const chest = tilt + (pose.bend ?? 0)
  const waist = along(hip, tilt, BODY.pelvis)
  const neckBase = along(waist, chest, BODY.chest)
  const shoulders = along(waist, chest, BODY.chest - BODY.shoulderDrop)
  const neckTop = along(neckBase, chest, BODY.neck)
  const side = (p: Vec, half: number, left: boolean, dir: number) =>
    along(p, dir + (left ? -90 : 90), half)

  const place = (limb: FrontLimb, root: Vec, a: number, b: number, tipLen: number) => {
    const target = limb.from === 'waist' ? inFrame(waist, tilt, limb.at) : limb.at
    const { mid, end } = limb.mid
      ? { mid: [root[0] + limb.mid[0], root[1] + limb.mid[1]] as Vec, end: target }
      : twoBone(root, target, a, b, limb.bend ?? 1)
    return { root, mid, end, tip: along(end, limb.angle ?? heading(mid, end), tipLen) }
  }
  const arm = (limb: FrontLimb, left: boolean) =>
    place(
      limb,
      side(shoulders, WIDTH.shoulder, left, chest),
      BODY.upperArm,
      BODY.forearm,
      BODY.hand,
    )
  const leg = (limb: FrontLimb, left: boolean) =>
    place(limb, side(hip, WIDTH.hip, left, tilt), BODY.thigh, BODY.shin, FOOT)

  return {
    hip,
    waist,
    shoulders,
    neckBase,
    neckTop,
    head: along(neckTop, chest, 9.5),
    armL: arm(pose.armL, true),
    armR: arm(pose.armR, false),
    legL: leg(pose.legL, true),
    legR: leg(pose.legR, false),
  }
}

function frontArm(j: FrontLimbJoints, tone: Tone): Shape[] {
  return [
    limb(j.root, j.mid, SIZE.upperArm, tone),
    limb(j.end, j.tip, SIZE.hand, tone),
    limb(j.mid, j.end, SIZE.forearm, tone),
    ball(j.end, SIZE.joint.wrist, tone),
    ball(j.mid, SIZE.joint.elbow, tone),
    ball(j.root, SIZE.joint.shoulder, tone),
  ]
}

function frontLeg(j: FrontLimbJoints, tone: Tone): Shape[] {
  return [
    limb(j.mid, j.end, SIZE.shin, tone),
    limb(j.end, j.tip, [3.8, 3.2], tone),
    ball(j.end, SIZE.joint.ankle, tone),
    limb(j.root, j.mid, SIZE.thigh, tone),
    ball(j.mid, SIZE.joint.knee, tone),
  ]
}

/** Hips, waist and chest, wider than deep, and a faceless oval head: it faces you. */
function frontTrunk(j: FrontJoints, tilt: number, tone: Tone): Shape[] {
  return [
    limb(along(j.hip, tilt, -3), j.waist, [13.5, 12], tone),
    limb(j.waist, j.shoulders, [12, 16], tone),
  ]
}

function frontHead(j: FrontJoints, tilt: number, tone: Tone): Shape[] {
  const [rx, ry] = [8, 11.5]
  const points = Array.from({ length: 24 }, (_, i) => {
    const a = (i / 24) * 2 * Math.PI
    return along(along(j.head, tilt - 90, rx * Math.cos(a)), tilt, ry * Math.sin(a))
  })
  return [
    limb(j.neckBase, j.neckTop, SIZE.neck, tone),
    { kind: 'path', d: smooth(points.map(svg)), tone },
  ]
}

export const FRONT_ORDER: readonly FrontPart[] = ['legL', 'armL', 'legR', 'torso', 'head', 'armR']

/** Everything to draw for ``pose`` seen from the front, back to front. The person's left side
 * is drawn in the far tone. */
export function frontShapes(
  pose: FrontPose,
  props: Props = {},
  order: readonly FrontPart[] = FRONT_ORDER,
): Shape[] {
  const j = solveFront(pose)
  const out = scenery(props)
  for (const part of order) {
    if (part === 'armL') out.push(...frontArm(j.armL, 'far'))
    else if (part === 'armR') out.push(...frontArm(j.armR, 'near'))
    else if (part === 'legL') out.push(...frontLeg(j.legL, 'far'))
    else if (part === 'legR') out.push(...frontLeg(j.legR, 'near'))
    else if (part === 'torso') out.push(...frontTrunk(j, pose.tilt, 'near'))
    else out.push(...frontHead(j, pose.tilt + (pose.bend ?? 0), 'near'))
  }
  return out
}
