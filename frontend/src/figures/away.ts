/**
 * The away versions' kit-free pulls (ADR-0086, #539): rows and curls holding a door frame, by
 * seed slug, and the ladder steps that change them (ADR-0063, addendum). The row is seen from the
 * side, the frame's upright in front of you; the curl leans sideways, away from the frame beside
 * you, so it is seen from the front only. Pose keys are as in poses.ts.
 */
import { BODY, dist, solve, type Pose, type Vec } from './body'
import { solveFront, type FrontPose } from './front'
import type { Camera, Vec3 } from './perspective'
import type { Figure } from './poses'

type Change = Partial<Figure>

/** How high the door frame is. */
const LINTEL = 205

/** The angle in ``[lo, hi]`` where ``f`` reaches ``target``, on the side of its lowest point
 * towards ``hi``, where it rises. */
function solveFor(f: (angle: number) => number, target: number, lo: number, hi: number): number {
  for (let a = lo; a <= hi; a++) if (f(a) < f(lo)) lo = a
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2
    if (f(mid) < target) lo = mid
    else hi = mid
  }
  return (lo + hi) / 2
}

// ---------------------------------------------------------------- the row, from the side

/** The frame's upright in front of you, its near face at ``FRAME``; the hands hold it at chest
 * height, a little in front of its face as a fist wraps round it. */
const FRAME = 40
const GRIP: Vec = [FRAME - 2, 106]
const LEG = BODY.thigh + BODY.shin - 0.1

/** Standing straight from the heels at ``heel`` (x), leaning back ``back`` degrees (forward when
 * less than 0), both hands on the frame. */
const leaning = (heel: number, back: number, armF?: Pose['armF']): Pose => {
  const rad = (back * Math.PI) / 180
  return {
    hip: [heel - LEG * Math.sin(rad), 7 + LEG * Math.cos(rad)],
    lean: -back,
    legN: { at: [heel, 7] },
    legF: { at: [heel + 3, 7] },
    armN: { at: GRIP, angle: 90, hand: 0.6 },
    armF: armF ?? { at: [GRIP[0] + 1, GRIP[1]], angle: 90, hand: 0.6 },
  }
}

/** The lean at which the shoulders are ``reach`` cm from the hands, the heels at ``heel``. */
const leanFor = (heel: number, reach: number) =>
  solveFor((back) => dist(solve(leaning(heel, back)).shoulder, GRIP), reach, -40, 60)

/** A row with the heels at ``heel``: arms straight, then the chest pulled in to the frame. */
const row = (heel: number, armF?: Pose['armF']): Pick<Figure, 'start' | 'end'> => ({
  start: leaning(heel, leanFor(heel, 54), armF),
  end: leaning(heel, leanFor(heel, 34), armF),
})

/** Toes level with the frame. */
const AT_FRAME = FRAME - 14

// ---------------------------------------------------------------- the curl, from the front

/** Seen from in front of you through the doorway: the upright you hold on your left (on the
 * right of the picture), the other one and the top of the frame. */
const FACING: Camera = { at: [0, 125, 330], look: [0, 100, 0] }
const box = (lo: Vec3, hi: Vec3) => [lo, hi] as const
const DOORWAY = {
  pads: [
    box([34, 0, -6], [42, LINTEL, 6]),
    box([-96, 0, -6], [-88, LINTEL, 6]),
    box([-96, LINTEL, -6], [42, LINTEL + 8, 6]),
  ],
}
/** The left hand on the frame at waist height, palm up. */
const HOLD: Vec = [32, 98]

/** Standing straight from the feet, centred at ``feet`` (x), leaning ``away`` degrees to your
 * right, away from the frame; the left hand on it with the elbow at ``elbow`` from the shoulder
 * (none: the arm straight), the right hand resting on the hip. */
const sideways = (feet: number, away: number, elbow?: Vec): FrontPose => {
  const rad = ((90 + away) * Math.PI) / 180
  const reach = 83 // the knees a touch soft, so the feet stay down as the hips tilt
  return {
    hip: [feet + reach * Math.cos(rad), 7 + reach * Math.sin(rad)],
    tilt: 90 + away,
    legL: { at: [feet + 9, 7] },
    legR: { at: [feet - 9, 7] },
    armL: elbow ? { at: HOLD, mid: elbow, angle: 0 } : { at: HOLD, angle: 0 },
    armR: { at: [-16, 4], from: 'waist', bend: -1 },
  }
}

/** The lean at which the left shoulder is ``reach`` cm from the hand, the feet at ``feet``. */
const awayFor = (feet: number, reach: number) =>
  solveFor((away) => dist(solveFront(sideways(feet, away)).armL.root, HOLD), reach, -20, 45)

/** The elbow of an arm curled to the hand on the frame: the upper arm hanging from the shoulder,
 * the forearm up to the hand. */
const curledElbow = (pose: FrontPose): Vec => {
  const shoulder = solveFront(pose).armL.root
  const d = dist(shoulder, HOLD)
  const [a, b] = [BODY.upperArm, BODY.forearm]
  const along = (a * a - b * b + d * d) / (2 * d)
  const off = Math.sqrt(Math.max(0, a * a - along * along))
  const [ux, uy] = [(HOLD[0] - shoulder[0]) / d, (HOLD[1] - shoulder[1]) / d]
  return [ux * along + uy * off, uy * along - ux * off] // below the line, elbow down
}

/** The elbow of a straight arm, a third of the way along from the shoulder to the hand, given so
 * it blends with a curled one. */
const straightElbow = (pose: FrontPose): Vec => {
  const shoulder = solveFront(pose).armL.root
  const share = BODY.upperArm / dist(shoulder, HOLD)
  return [(HOLD[0] - shoulder[0]) * share, (HOLD[1] - shoulder[1]) * share]
}

/** A curl with the feet at ``feet``: hanging from the frame on a straight arm, then curled in. */
const curl = (feet: number): NonNullable<Figure['front']> => {
  const start = sideways(feet, awayFor(feet, BODY.upperArm + BODY.forearm - 1))
  const end = sideways(feet, awayFor(feet, 38))
  return {
    view: [-125, 85, -110, 125],
    camera: FACING,
    standing: true,
    only: true,
    machine: DOORWAY,
    start: { ...start, armL: { ...start.armL, mid: straightElbow(start) } },
    end: { ...end, armL: { ...end.armL, mid: curledElbow(end) } },
  }
}

/** The curl seen from the side is a curl in place, for the poses every figure has. */
const SIDE_CURL = {
  start: {
    hip: [0, 93.5],
    lean: 0,
    legN: { at: [0, 7] },
    legF: { at: [3, 7] },
    armN: { at: [1.5, 81.54], mid: [0, -30] },
    armF: { dir: -92, reach: 0.995 },
  },
  end: {
    hip: [0, 93.5],
    lean: 0,
    legN: { at: [0, 7] },
    legF: { at: [3, 7] },
    armN: { at: [13, 130], mid: [0, -30] },
    armF: { dir: -92, reach: 0.995 },
  },
} as const satisfies Pick<Figure, 'start' | 'end'>

export const AWAY: Readonly<Record<string, Figure>> = {
  // Toes level with the frame, the body straight: the other steps move the feet or drop a hand.
  'doorway-row': {
    frames: [
      'Holding the door frame, toes level with it, leaning back, arms straight',
      'Chest pulled in to the frame, body still straight',
    ],
    view: [-96, 60, -3, LINTEL + 10],
    props: { wall: { x0: FRAME, x1: FRAME + 9, top: LINTEL } },
    tempo: [1000, 400, 1600, 400],
    ...row(AT_FRAME),
  },
  // Feet in at the frame: the first step stands further off it.
  'doorway-curl': {
    frames: [
      'Side on in the doorway, a hand on the frame, leaning away on a straight arm',
      'Curled back in to the frame, the elbow still',
    ],
    view: [-40, 60, -3, 182],
    tempo: [1000, 400, 1800, 400],
    ...SIDE_CURL,
    front: curl(14),
  },
}

export const AWAY_STEPS: Readonly<Record<string, Readonly<Record<string, Change>>>> = {
  'doorway-row': {
    'Upright, a step back': {
      frames: [
        'A step back from the frame, nearly upright, arms straight',
        'Pulled in to the frame',
      ],
      ...row(AT_FRAME - 50),
    },
    'Leaning back, half a step in': {
      frames: ['Half a step in, leaning back, arms straight', 'Chest pulled in to the frame'],
      ...row(AT_FRAME - 25),
    },
    'One arm, feet at the frame': {
      frames: [
        'One hand on the frame, toes level with it, leaning back',
        'Chest pulled in, shoulders level',
      ],
      ...row(AT_FRAME, { dir: -95, reach: 0.995 }),
    },
  },
  'doorway-curl': {
    'Leaning back a little': {
      frames: [
        'A step back from the frame, a hand on it, leaning away a little',
        'Curled back in to the frame',
      ],
      front: curl(-2),
    },
  },
}
