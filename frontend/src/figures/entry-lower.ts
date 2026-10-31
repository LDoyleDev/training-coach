/**
 * The entry exercises' figures for the lower body, the core, balance and walking (ADR-0083), by
 * seed slug, and the ladder steps that change them (ADR-0063, addendum). Pose keys are as in
 * poses.ts. A hold (a plank, a balance) barely moves, so its two frames are the set-up and the
 * hold.
 */
import { BODY, solve, type Pose, type Vec } from './body'
import type { FrontLimb, FrontPose } from './front'
import type { Figure } from './poses'
import { STAIR, WORKTOP, railAt } from './shapes'

type Change = Partial<Figure>

const STAND = { legN: { at: [0, 7] }, legF: { at: [3, 7] } } as const
const HANG = { armN: { dir: -88, reach: 0.995 }, armF: { dir: -86, reach: 0.995 } } as const
/** A kitchen counter in front of you, its edge at ``x``. */
const counter = (x: number) => ({ wall: { x0: x, x1: x + 30, top: WORKTOP } })
const rad = (d: number) => (d * Math.PI) / 180

// ---------------------------------------------------------------- step-up

/** The bottom stair of a flight, or a low step, in front of you: one foot on it, then standing
 * tall on it, the back foot lifted behind its edge. */
const STAIRS = { x: 12, rise: 18 }
const stepUp = (rise: number): Pick<Figure, 'start' | 'end'> => ({
  start: {
    hip: [0, 93.5 - 0.3 * rise],
    lean: 14,
    legN: { at: [20, rise + 7] },
    legF: { at: [-14, 7] },
    ...HANG,
  },
  end: {
    hip: [18, 85 + rise + 7],
    lean: 2,
    legN: { at: [20, rise + 7] },
    legF: { at: [-12, rise + 10], angle: -20 },
    ...HANG,
  },
})
const STEP_UP = stepUp(STAIRS.rise)

/** The near hand on the banister, ``x`` cm along it, ahead of you. */
const onRail = (pose: Pose, x: number): Pose => ({
  ...pose,
  armN: {
    at: [x, railAt(STAIRS, x) + 3],
    angle: (Math.atan(STAIRS.rise / STAIR.run) * 180) / Math.PI,
  },
})

/** Something held in the near hand, on the stepping leg's side. */
const holding = (pose: Pose): Pose => ({ ...pose, armN: { dir: -97, reach: 0.995 } })

// ---------------------------------------------------------------- plank

/** A plank in one straight line from the balls of the feet at ``ball``, the body ``angle``
 * degrees up from the floor, placed by the hip so it can blend with a pose that isn't straight
 * (knees down, or the feet walked in); the hands at ``hands``, flat. */
const line = (ball: Vec, angle: number, hands: Vec): Pose => {
  const arms = {
    armN: { at: hands, angle: 0 },
    armF: { at: [hands[0] + 2.7, hands[1]] as Vec, angle: 0 },
  }
  const j = solve({ plank: { ball, angle }, lean: 0, ...arms, legN: {}, legF: {} })
  const leg = { at: j.legN.ankle, angle: angle - 90, floor: ball[1] }
  return { hip: j.hip, lean: 90 - angle, legN: leg, legF: { ...leg }, ...arms }
}

/** A straight plank at ``angle`` whose shoulders are an arm's length (53 cm) from ``hands``:
 * the balls of the feet go where that puts them. */
const ARM = 53
const toHands = (hands: Vec, angle: number): Pose => {
  const s = solve(line([0, 0], angle, hands)).shoulder // from the balls of the feet at 0
  const down = Math.asin((hands[1] - s[1]) / ARM)
  return line([hands[0] - s[0] - ARM * Math.cos(down), 0], angle, hands)
}

/** Hands on something ``top`` cm high at x = 100: the feet walked in, the body at ``walkedIn``
 * degrees, then back until it is one straight slope at ``angle``; lower takes more weight on the
 * arms. */
const incline = (
  top: number,
  [walkedIn, angle]: readonly [number, number],
  props: Figure['props'],
  frames: Figure['frames'],
): Change => {
  const hands: Vec = [100, top + 2.5]
  const end = toHands(hands, angle)
  const start = toHands(hands, walkedIn)
  const x0 = Math.floor(end.legN.at![0] - 22)
  return { frames, props, view: [x0, 172, -3, 188], start, end }
}

/** The full plank on the hands, as the push-up's top: its two frames set it up from the knees. */
const FLOOR_HANDS: Vec = [118.3, 3]
const PLANK = line([-2.2, 0], 19.7, FLOOR_HANDS)

/** On the knees with the hands where the plank has them: the feet where they are, the knees down
 * on the floor in front of them, the hips bent. */
const kneesDown = (pose: Pose): Pose => {
  const ankle = pose.legN.at!
  const knee: Vec = [ankle[0] + Math.sqrt(43 ** 2 - (ankle[1] - 5.4) ** 2), 5.4]
  const hip: Vec = [knee[0] + 44 * Math.cos(rad(62)), knee[1] + 44 * Math.sin(rad(62))]
  // The trunk aims the shoulder an arm's length from the hands.
  const hands = pose.armN.at!
  const d = Math.hypot(hands[0] - hip[0], hands[1] - hip[1])
  const towards = Math.atan2(hands[1] - hip[1], hands[0] - hip[0])
  const up = towards + Math.acos((44 ** 2 + d ** 2 - ARM ** 2) / (2 * 44 * d))
  return { ...pose, hip, lean: 90 - (up * 180) / Math.PI }
}

/** A knee plank: kneeling on a cushion, the hands under the shoulders, from the hips bent to knees
 * to head in one line. */
const KNEE: Vec = [0.1, 5.4]
const KNEELING = {
  legN: { at: [-42.5, 11.6], angle: -100 },
  legF: { at: [-40, 11.6], angle: -100 },
} as const
const ON_KNEES: Change = {
  frames: ['On your knees, hands under your shoulders', 'Hips forward: knees to head in one line'],
  view: [-60, 106, -3, 86],
  props: { mat: [-50, 90] },
  order: ['armF', 'legF', 'legN', 'armN', 'torso', 'head'],
  start: {
    kneel: { knee: KNEE, angle: 48 },
    lean: 25,
    ...KNEELING,
    armN: { at: [71, 3], angle: 0 },
    armF: { at: [73.7, 3], angle: 0 },
  },
  end: {
    kneel: { knee: KNEE, angle: 34 },
    lean: 0,
    ...KNEELING,
    armN: { at: [71, 3], angle: 0 },
    armF: { at: [73.7, 3], angle: 0 },
  },
}

/** A full plank reaching one arm forward, level with the shoulder. */
const reach = (pose: Pose): Pose => {
  const s = solve(pose).shoulder
  return { ...pose, armN: { at: [s[0] + 54, s[1] - 3], angle: 0 } }
}

// ---------------------------------------------------------------- knee lift and toe lift

/** Sitting tall near the front of a chair, its back on the left, the feet flat in front. */
const CHAIR = { chair: { x0: -38, x1: 10, seat: 45 } }
const SEATED = {
  hip: [0, 53],
  lean: 0,
  legN: { at: [44, 7] },
  legF: { at: [47, 7] },
} as const
const HANDS_ON_SEAT = {
  armN: { at: [6, 49], angle: 0 },
  armF: { at: [7, 49], angle: 0 },
} as const
const HANDS_ON_THIGHS = {
  armN: { at: [25, 61], angle: -4 },
  armF: { at: [26, 61], angle: -4 },
} as const

/** Side on to the counter, beside you on the far side: the far hand on its worktop. */
const BESIDE: readonly [number, number] = [-46, 56]
const FAR_ON_TOP = { at: [19, WORKTOP + 2.5], angle: -4 } as const
const FAR_OVER = { at: [19, WORKTOP + 9], angle: 0 } as const

// ---------------------------------------------------------------- balance

/** Standing tall facing the counter, the feet together, the hands on its edge or just over it. */
const FACING = (hands: number, neck = 0): Pose => ({
  hip: [0, 93.5],
  lean: 3,
  neck,
  legN: { at: [0, 7] },
  legF: { at: [2, 7] },
  armN: { at: [31, hands], angle: 0 },
  armF: { at: [33, hands], angle: 0 },
})

/** Standing beside the counter, the far hand on it or ready just over it, the feet as given. */
const beside = (
  far: Pose['armF'],
  legN: Pose['legN'] = { at: [0, 7] },
  hip: Vec = [0, 93.5],
): Pose => ({
  hip,
  lean: 1,
  legN,
  legF: { at: [2, 7] },
  armN: { dir: -89, reach: 0.995 },
  armF: far,
})

/** A leg seen from the front whose ankle is ``z`` cm towards you (+) or away (-): the knee worked
 * out in the round, bending towards you, and given as seen, so the leg keeps its length. */
const leg3 = (root: Vec, ankle: Vec, z: number): FrontLimb => {
  const [dx, dy] = [ankle[0] - root[0], ankle[1] - root[1]]
  const d = Math.min(Math.hypot(dx, dy, z), BODY.thigh + BODY.shin - 0.01)
  const u = [dx / d, dy / d, z / d]
  const along = (BODY.thigh ** 2 - BODY.shin ** 2 + d ** 2) / (2 * d)
  const out = Math.sqrt(BODY.thigh ** 2 - along ** 2)
  // Square to the leg, towards you.
  const p = [-u[2] * u[0], -u[2] * u[1], 1 - u[2] * u[2]]
  const pl = Math.hypot(...p)
  const knee = [0, 1, 2].map((i) => u[i] * along + (p[i] / pl) * out)
  return { at: ankle, mid: [knee[0], knee[1]], toward: [knee[2], z] }
}

/** Standing beside the counter, seen from in front and off to the right, so the feet show one in
 * front of the other: the counter on the left side, the left hand ready over it. The left foot
 * goes ``ahead`` cm in front of the right, ``apart`` cm between them. */
const standingFront = (ahead: number, apart: number): FrontPose => {
  // As tall as the stance lets the legs stay nearly straight.
  const hip: Vec = [0, 7 + Math.sqrt(86.6 ** 2 - (ahead / 2) ** 2 - (9 - apart / 2) ** 2)]
  return {
    hip,
    tilt: 90,
    legL: leg3([hip[0] + 9, hip[1]], [apart / 2, 7], ahead / 2),
    legR: leg3([hip[0] - 9, hip[1]], [-apart / 2, 7], -ahead / 2),
    armL: { at: [34, WORKTOP + 9] },
    armR: { at: [-21, hip[1] - 10], bend: -1 },
  }
}

/** Feet together, then one foot stepped ``ahead`` cm in front of the other, the hips between;
 * from the front, the feet ``apart`` cm side to side, in one line when heel to toe. */
const tandem = (ahead: number, apart: number, frames: Figure['frames']): Change => ({
  frames,
  props: { worktop: BESIDE },
  start: beside(FAR_OVER),
  end: beside(
    { ...FAR_OVER, at: [FAR_OVER.at[0] + ahead / 2, FAR_OVER.at[1]] },
    { at: [ahead, 7] },
    [ahead / 2, 92.6],
  ),
  front: {
    view: [-80, 100, -100, 112],
    camera: { at: [-90, 235, 290], look: [10, 72, 0] },
    standing: true,
    machine: {
      pads: [
        [
          [27, 0, -70],
          [95, WORKTOP, 4],
        ],
      ],
    },
    start: standingFront(0, 10),
    end: standingFront(ahead, apart),
  },
})

/** On one leg: the near foot lifted a little behind, the far hand as given. */
const oneLeg = (far: Pose['armF'], frames: Figure['frames']): Change => ({
  frames,
  props: { worktop: BESIDE },
  start: beside(far),
  end: beside(far, { at: [-9, 22], angle: -12 }),
})

// ---------------------------------------------------------------- deadlift

/** Both hands on the handle, together. */
const both = (at: Vec) =>
  ({ armN: { at, hand: 0.6 }, armF: { at: [at[0] + 1, at[1]] as Vec, hand: 0.6 } }) as const
const LIFTED = ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'] as const
/** A shopping bag on a stack of books in front of your feet, its handles at shin height. */
const BOOKS = { x0: 20, x1: 44, top: 16 }

export const ENTRY_LOWER: Readonly<Record<string, Figure>> = {
  // One stair, no hands: the other steps add a hand on a support, or something to carry.
  'step-up': {
    frames: [
      'One whole foot on the stair, the other on the floor',
      'Standing tall on it, the back foot lifted',
    ],
    view: [-32, 100, -3, 192],
    props: { stair: STAIRS },
    tempo: [1300, 400, 1600, 500],
    ...STEP_UP,
  },
  // The full plank: the other steps raise the hands, drop the knees, or reach.
  plank: {
    frames: ['Hands under your shoulders, knees down', 'Knees up: heels to head in one line, hold'],
    view: [-14, 174, -3, 86],
    props: { mat: [-12, 150] },
    order: ['armF', 'legF', 'legN', 'armN', 'torso', 'head'],
    tempo: [1300, 2600, 1100, 700],
    ease: 'sine',
    start: kneesDown(PLANK),
    end: PLANK,
  },
  // Standing at the counter, side on to it: the outside knee lifts to hip height.
  'knee-lift': {
    frames: [
      'Side on to the counter, a hand on it, standing tall',
      'The outside knee lifted to hip height',
    ],
    view: [-48, 70, -3, 182],
    props: { worktop: BESIDE },
    tempo: [1100, 500, 1500, 500],
    start: { hip: [0, 93.5], lean: 0, ...STAND, armN: HANG.armN, armF: FAR_ON_TOP },
    end: {
      hip: [0, 93.5],
      lean: 1,
      legN: { at: [44, 50.5], angle: -20 },
      legF: { at: [3, 7] },
      armN: HANG.armN,
      armF: FAR_ON_TOP,
    },
  },
  // A kettlebell from the floor between the feet; the bag from a block is a step.
  deadlift: {
    frames: [
      'Hips back, knees bent, both hands on the bell, back flat',
      'Standing tall, hips through, the bell close to your legs',
    ],
    view: [-48, 52, -3, 186],
    props: { bell: 'near' },
    order: LIFTED,
    tempo: [1100, 400, 1500, 500],
    start: { hip: [-28, 56], lean: 62, neck: -8, ...STAND, ...both([6, 22]) },
    end: { hip: [0, 93], lean: 0, ...STAND, ...both([4.5, 82]) },
  },
  'toe-lift': {
    frames: [
      'Sitting tall, feet flat in front of you',
      'Heels down, toes lifted as high as you can',
    ],
    view: [-42, 72, -3, 140],
    props: CHAIR,
    tempo: [800, 500, 1400, 400],
    start: { ...SEATED, legN: { at: [44, 7.3] }, legF: { at: [47, 7.3] }, ...HANDS_ON_THIGHS },
    end: {
      ...SEATED,
      legN: { at: [44, 7.3], angle: 35 },
      legF: { at: [47, 7.3], angle: 35 },
      ...HANDS_ON_THIGHS,
    },
  },
  // Feet together, both hands on the counter: looking down to set the feet, then ahead.
  balance: {
    frames: [
      'Feet together and touching, both hands on the counter',
      'Standing tall, eyes on a point ahead; hold still',
    ],
    view: [-40, 66, -3, 182],
    props: counter(30),
    tempo: [1400, 2600, 1400, 800],
    ease: 'sine',
    start: FACING(WORKTOP + 2.5, 20),
    end: FACING(WORKTOP + 2.5),
  },
  'interval-walk': {
    frames: ['Mid-stride: heel landing in front, arms swinging', 'The other leg and arm forward'],
    view: [-56, 64, -3, 182],
    tempo: [620, 0, 620, 0],
    ease: 'sine',
    start: {
      hip: [0, 88],
      lean: 4,
      legN: { at: [30, 6.6], angle: 20 },
      legF: { at: [-30, 12.6], angle: -30 },
      armN: { dir: -112, reach: 0.97 },
      armF: { dir: -64, reach: 0.97 },
    },
    end: {
      hip: [0, 88],
      lean: 4,
      legN: { at: [-30, 12.6], angle: -30 },
      legF: { at: [30, 6.6], angle: 20 },
      armN: { dir: -64, reach: 0.97 },
      armF: { dir: -112, reach: 0.97 },
    },
  },
}

const kettle = ENTRY_LOWER.deadlift

export const ENTRY_LOWER_STEPS: Readonly<Record<string, Readonly<Record<string, Change>>>> = {
  'step-up': {
    'Low step, hand on a support': {
      frames: ['One foot on a low step, a hand on the wall', 'Standing tall on the step'],
      view: [-32, 74, -3, 184],
      props: { step: { x0: 12, x1: 46, top: 10 }, wall: { x0: 46, x1: 54, top: 184 } },
      start: { ...stepUp(10).start, armN: { at: [42, 116], angle: 90 } },
      end: { ...stepUp(10).end, armN: { at: [42, 116], angle: 90 } },
    },
    'One stair, hand on the rail': {
      frames: [
        'One foot on the bottom stair, a hand on the banister',
        'Standing tall on the stair, the hand still on it',
      ],
      props: { stair: { ...STAIRS, rail: true } },
      start: onRail(STEP_UP.start, 46),
      end: onRail(STEP_UP.end, 46),
    },
    'One stair, holding a bag': {
      frames: [
        'A bag in the hand on the stepping side, one foot on the stair',
        'Standing tall on the stair, the bag at your side',
      ],
      props: { stair: { ...STAIRS, rail: true }, bag: 'near' },
      order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN', 'bell'],
      start: holding(STEP_UP.start),
      end: holding(STEP_UP.end),
    },
    'One stair, holding 8 kg': {
      frames: [
        'A bell in the hand on the stepping side, one foot on the stair',
        'Standing tall on the stair, the bell at your side',
      ],
      props: { stair: { ...STAIRS, rail: true }, bell: 'near' },
      order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN', 'bell'],
      start: holding(STEP_UP.start),
      end: holding(STEP_UP.end),
    },
  },
  plank: {
    'Hands on a counter': incline(WORKTOP, [68, 52], counter(98), [
      'Hands on the counter, feet close',
      'Feet walked back: a straight slope, hold',
    ]),
    'Hands on a table': incline(74, [58, 44], { bench: { x0: 95, x1: 168, top: 74 } }, [
      'Hands on a table, feet close',
      'Feet walked back: a straight slope, hold',
    ]),
    'Hands on a chair seat against a wall': incline(
      45,
      [38, 32],
      { chair: { x0: 142, x1: 96, seat: 45 }, wall: { x0: 143, x1: 150, top: 150 } },
      [
        'Hands on a chair seat, the chair against a wall',
        'Feet walked back: one straight line, hold',
      ],
    ),
    'On the knees': ON_KNEES,
    'Full plank, arm reach': {
      frames: ['Full plank, hands under your shoulders', 'One arm reached forward, hips still'],
      view: [-14, 194, -3, 86],
      tempo: [1000, 1000, 1000, 800],
      order: ['armF', 'legF', 'legN', 'torso', 'head', 'armN'],
      start: PLANK,
      end: reach(PLANK),
    },
  },
  'knee-lift': {
    'Seated march': {
      frames: [
        'Sitting tall near the front of a chair, hands on the seat',
        'One knee lifted a hand’s width, then the other',
      ],
      view: [-42, 72, -3, 140],
      props: CHAIR,
      tempo: [700, 300, 900, 300],
      start: { ...SEATED, ...HANDS_ON_SEAT },
      end: { ...SEATED, legN: { at: [42, 17], angle: 0 }, ...HANDS_ON_SEAT },
    },
  },
  deadlift: {
    'A bag, from a block': {
      frames: [
        'A bag on a stack of books, handles at shin height; hips back',
        'Standing tall, the bag close to your legs',
      ],
      view: [-40, 60, -3, 186],
      props: { step: BOOKS, bag: 'near' },
      start: { hip: [-12, 74], lean: 56, neck: -8, ...STAND, ...both([32, 47]) },
      end: { ...kettle.end, ...both([4.5, 82]) },
    },
  },
  balance: {
    'Feet together, hands over the counter': {
      frames: ['Feet together, hands on the counter', 'Hands lifted just above it; hold still'],
      start: FACING(WORKTOP + 2.5),
      end: FACING(WORKTOP + 9),
    },
    'Half heel-to-toe, beside the counter': tandem(17, 9, [
      'Beside the counter, feet together, a hand ready over it',
      'One heel beside the other foot’s big toe; hold',
    ]),
    'Heel-to-toe, beside the counter': tandem(22, 3, [
      'Beside the counter, feet together, a hand ready over it',
      'One foot right in front of the other, heel to toes; hold',
    ]),
    'One leg, a fingertip on the counter': oneLeg(FAR_ON_TOP, [
      'Beside the counter, a fingertip on it',
      'One foot lifted a little off the floor; hold',
    ]),
    'One leg, beside the counter': oneLeg(FAR_OVER, [
      'Beside the counter, a hand ready over it',
      'One foot lifted, not touching the counter; hold',
    ]),
    'One leg, turning your head': oneLeg(FAR_OVER, [
      'On one leg beside the counter, a hand ready over it',
      'Slowly look left and right as you hold',
    ]),
    'One leg, eyes closed': oneLeg(FAR_OVER, [
      'Beside the counter, a hand ready over it',
      'One foot lifted, eyes closed; hold',
    ]),
  },
}
