/**
 * The steps ADR-0083 added below the bottom of today's ladders (#508, #534), drawn over their
 * exercise's figure (ADR-0063, addendum): a push-up from a wall down to the floor, split squats
 * holding a chair, a pull-up with the feet on a chair, household loads in place of a kettlebell,
 * calf raises on both legs and a Copenhagen plank with the bottom foot helping. Pose keys are as
 * in poses.ts.
 */
import { BODY, solve, type Pose, type Vec } from './body'
import { KNEE, KNEELING, ballFor, line } from './entry-lower'
import { FIGURES, type Figure } from './poses'
import { WORKTOP } from './shapes'

type Change = Partial<Figure>

// ---------------------------------------------------------------- push-up

/** A kitchen counter in front of you, its edge at ``x``. */
const counter = (x: number) => ({ wall: { x0: x, x1: x + 30, top: WORKTOP } })

/** A push-up with the hands on something ``top`` cm high at x = 100: arms straight, the body in
 * one slope at ``high`` degrees from the floor, then lowered about the balls of the feet to
 * ``low``, the chest to the edge. */
const inclined = (
  top: number,
  [high, low]: readonly [number, number],
  props: Figure['props'],
  frames: Figure['frames'],
): Change => {
  const hands: Vec = [100, top + 2.5]
  const ball = ballFor(hands, high)
  const end = line(ball, low, hands)
  return {
    frames,
    props,
    view: [Math.floor(end.legN.at![0] - 22), 172, -3, Math.max(100, top + 110)],
    start: line(ball, high, hands),
    end,
  }
}

/** Palms flat on a wall, fingers up: the push-up standing. */
const WALL_X = 103
const onWall = (pose: Pose): Pose => ({
  ...pose,
  armN: { ...pose.armN, angle: 90 },
  armF: { ...pose.armF, angle: 90 },
})
const wall = (height: number, [high, low]: readonly [number, number]): Change => {
  const hands: Vec = [WALL_X - 3, height]
  const ball = ballFor(hands, high)
  return {
    frames: ['Hands on the wall at shoulder height, feet a step back', 'Chest to the wall'],
    props: { wall: { x0: WALL_X, x1: WALL_X + 8, top: 200 } },
    view: [Math.floor(ball[0] - 30), WALL_X + 14, -3, 190],
    start: onWall(line(ball, high, hands)),
    end: onWall(line(ball, low, hands)),
  }
}

/** On the knees, from knees to head in one line, the hands under the chest. */
const KNEE_HANDS: Vec = [78, 3]
const kneeLine = (angle: number): Pose => ({
  kneel: { knee: KNEE, angle },
  lean: 0,
  ...KNEELING,
  armN: { at: KNEE_HANDS, angle: 0 },
  armF: { at: [KNEE_HANDS[0] + 2.7, KNEE_HANDS[1]], angle: 0 },
})

const PUSH_UP: Readonly<Record<string, Change>> = {
  'Hands on a wall': wall(130, [74, 64]),
  'Hands on a counter': inclined(WORKTOP, [52, 42], counter(98), [
    'Hands on the edge of the counter, body straight',
    'Chest to the edge, elbows bent',
  ]),
  'Hands on a table': inclined(74, [44, 34], { bench: { x0: 95, x1: 168, top: 74 } }, [
    'Hands on a table, body straight',
    'Chest to the edge, elbows bent',
  ]),
  'Hands on a chair seat against a wall': inclined(
    45,
    [32, 22],
    { chair: { x0: 142, x1: 96, seat: 45 }, wall: { x0: 143, x1: 150, top: 150 } },
    ['Hands on the front of a chair seat, the chair against a wall', 'Chest to the seat'],
  ),
  'On the knees': {
    frames: [
      'On your knees, arms straight, knees to head in one line',
      'Chest a fist above the floor',
    ],
    view: [-60, 130, -3, 92],
    props: { mat: [-50, 120] },
    start: kneeLine(34),
    end: kneeLine(9),
  },
  'Hands on a stair or low step': inclined(18, [24, 12], { step: { x0: 94, x1: 128, top: 18 } }, [
    'Hands on a low step, body straight',
    'Chest to the edge of the step',
  ]),
}

// ---------------------------------------------------------------- split squat

/** Both feet on the floor, the back one a long step behind on its toes; the near hand on the back
 * of a chair in front of you. */
const BACK_TOES = { at: [-58, 13.7], angle: -40 } as const
const CHAIR_AHEAD = { x0: 14, x1: 58, seat: 45 }
const HAND_ON_CHAIR = { at: [16, 93], angle: 0 } as const
const splitOnFloor = (hip: Vec, lean: number): Pose => ({
  hip,
  lean,
  legN: { at: [0, 7] },
  legF: BACK_TOES,
  armN: HAND_ON_CHAIR,
  armF: { dir: -100, reach: 0.995 },
})
const holdingChair = (bottom: Vec, frames: Figure['frames']): Change => ({
  frames,
  view: [-90, 80, -3, 178],
  props: { chair: CHAIR_AHEAD },
  order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
  start: splitOnFloor([-26, 86], 4),
  end: splitOnFloor(bottom, 8),
})

/** The back foot on the bottom stair or a low step behind you, its ball on the edge. */
const LOW_STEP = { x0: -96, x1: -60, top: 18 }
const SPLIT: Readonly<Record<string, Change>> = {
  'Holding a chair, short range': holdingChair(
    [-27, 72],
    ['A long step apart, back heel up, a hand on a chair', 'Both knees bent a little way'],
  ),
  'Holding a chair, full range': holdingChair(
    [-29, 52],
    ['A long step apart, back heel up, a hand on a chair', 'Back knee just above the floor'],
  ),
  'Back foot on a low step': {
    frames: ['Back foot on a low step behind you, standing tall', 'Back knee just above the floor'],
    view: [-100, 50, -3, 178],
    props: { step: LOW_STEP },
    start: {
      hip: [-16, 90],
      lean: 6,
      legN: { at: [0, 7] },
      legF: { at: [-66, 31.7], angle: -40, floor: 18 },
      armN: { dir: -40, reach: 0.45 },
      armF: { dir: -38, reach: 0.45 },
    },
    end: {
      hip: [-22, 50],
      lean: 14,
      spine: 2,
      legN: { at: [0, 7] },
      legF: { at: [-66, 31.7], angle: -40, floor: 18 },
      armN: { dir: -40, reach: 0.45 },
      armF: { dir: -38, reach: 0.45 },
    },
  },
}

// ---------------------------------------------------------------- pull-up

const pull = FIGURES['pull-up']
/** The pull-up's hang, ``rise`` cm up with the chest lifted: the shoulders drawn down. */
const hang = (rise: number, lean: number, spine = 0): Pose => {
  const { hip, legN, legF, armN, armF } = pull.start
  const up = (at: Vec): Vec => [at[0], at[1] + rise]
  return {
    hip: up(hip!),
    lean,
    spine,
    legN: { ...legN, at: up(legN.at!) },
    legF: { ...legF, at: up(legF.at!) },
    armN, // drawn as the pull-up's hang: elbows out to the sides, arms straight
    armF,
  }
}

/** A sturdy chair under a bar at door-frame height: on the balls of the feet on the seat, knees
 * bent, arms straight; higher on the toes as the legs push, chin over the bar. */
const LOW_BAR = 195
const GRIP: Vec = [0, LOW_BAR - 4.5]
/** The elbow of an arm straight up to the bar, given so it blends with the bent arm at the top. */
const straightUp = (pose: Pose, hand: Vec): Vec => {
  const shoulder = solve(pose).shoulder
  const share = BODY.upperArm / Math.hypot(hand[0] - shoulder[0], hand[1] - shoulder[1])
  return [(hand[0] - shoulder[0]) * share, (hand[1] - shoulder[1]) * share]
}
const CROUCHED: Pose = {
  hip: [-2, LOW_BAR - 101],
  lean: -4,
  legN: { at: [-16, 56], angle: -20, floor: 45 },
  legF: { at: [-13, 56], angle: -20, floor: 45 },
  armN: { at: GRIP, angle: 90 },
  armF: { at: GRIP, angle: 90 },
}
const ASSISTED: Change = {
  frames: [
    'Feet on a chair under the bar, knees bent, arms straight',
    'Chin over the bar, the legs helping',
  ],
  view: [-56, 60, -3, 230],
  props: { bar: [0, LOW_BAR], chair: { x0: -46, x1: 4, seat: 45 } },
  start: {
    ...CROUCHED,
    armN: { at: GRIP, mid: straightUp(CROUCHED, GRIP), angle: 90 },
    armF: { at: GRIP, mid: straightUp(CROUCHED, GRIP), angle: 90 },
  },
  end: {
    hip: [-2, LOW_BAR - 50],
    lean: -9,
    spine: -6,
    neck: -8,
    legN: { at: [-9.2, 59.46], angle: -50, floor: 45 },
    legF: { at: [-6.2, 59.46], angle: -50, floor: 45 },
    armN: { at: GRIP, mid: [-2, -19], angle: 90 },
    armF: { at: GRIP, mid: [-1, -19], angle: 90 },
  },
}

const PULL_UP: Readonly<Record<string, Change>> = {
  'Feet on a chair': ASSISTED,
  'Scapular pulls': {
    frames: [
      'Hanging, arms straight, shoulders up by your ears',
      'Shoulders pulled down and back, chest up',
    ],
    tempo: [900, 600, 1500, 500],
    start: hang(0, -3),
    end: hang(2, -4, -2),
  },
}

// ---------------------------------------------------------------- household loads

const row = FIGURES['kb-row']
const curl = FIGURES['kb-curl']
/** One arm at a time: the far arm hangs at your side. */
const farDown = (pose: Pose): Pose => ({ ...pose, armF: { dir: -92, reach: 0.995 } })

const LOADS: Readonly<Record<string, Readonly<Record<string, Change>>>> = {
  'kb-row': {
    'A bag, about 4 kg': {
      frames: [
        'Hand and knee on the bench, a bag hanging from the other hand',
        'Bag pulled to your hip',
      ],
      props: { bench: row.props!.bench, bag: 'near' },
    },
  },
  'kb-curl': {
    'Water bottles, about 1 kg': {
      frames: [
        'Standing tall, a bottle in each hand, elbows at your sides',
        'Curled up, elbows still at your sides',
      ],
      props: { bottles: true },
    },
    'A bag, 2-4 kg': {
      frames: [
        'A bag by its handles in one hand, elbow at your side',
        'Curled up, the elbow still at your side',
      ],
      props: { bag: 'near' },
      start: farDown(curl.start),
      end: farDown(curl.end),
    },
  },
}

// ---------------------------------------------------------------- calf raise

const calf = FIGURES['calf-raise']
/** Both feet: the far foot beside the near one. */
const both = (pose: Pose): Pose => ({
  ...pose,
  legF: { ...pose.legN, at: [pose.legN.at![0] + 3, pose.legN.at![1]] },
})
/** Standing on the flat floor facing the wall, hands on it at chest height: heels down, or up on
 * the balls of the feet, which stay put. */
const flat = (up: boolean): Pose => {
  const ankle: Vec = up ? [6.37, 13.19] : [0, 7]
  const foot = up ? -35 : 0
  return {
    hip: [ankle[0] - 1, ankle[1] + 86.5],
    lean: 3,
    legN: { at: ankle, angle: foot },
    legF: { at: [ankle[0] + 3, ankle[1]], angle: foot },
    armN: { at: [37, 128], angle: 90 },
    armF: { at: [37, 129], angle: 90 },
  }
}
const CALF: Readonly<Record<string, Change>> = {
  'Both legs, hands on a wall': {
    frames: ['On the flat floor, hands on the wall', 'Up on your toes as high as you can, pause'],
    view: [-40, 60, -3, 190],
    props: { wall: { x0: 40, x1: 45, top: 200 } },
    inset: undefined,
    start: flat(false),
    end: flat(true),
  },
  'Both legs, on a step': {
    frames: ["Both feet on the step's edge, heels below it", 'Heels up as high as you can, pause'],
    start: both(calf.start),
    end: both(calf.end),
  },
}

// ---------------------------------------------------------------- Copenhagen plank

const copenhagen = FIGURES['copenhagen-plank']
/** The bottom foot stays on the floor under the chair, pushing to help lift the hips. */
const FOOT_SIDE = { at: [-118, 5], angle: 180, bend: -1 } as const
const FOOT_FRONT = { at: [-118, 5] } as const
const HELPING: Change = {
  frames: [
    'On your side, top knee on a chair, bottom foot on the floor under it',
    'Hips up, pushing through the top knee and the bottom foot',
  ],
  start: { ...copenhagen.start, legF: FOOT_SIDE },
  end: { ...copenhagen.end, legF: FOOT_SIDE },
  front: copenhagen.front && {
    ...copenhagen.front,
    start: { ...copenhagen.front.start, legL: FOOT_FRONT },
    end: { ...copenhagen.front.end, legL: FOOT_FRONT },
  },
}

export const LADDER_DOWN_STEPS: Readonly<Record<string, Readonly<Record<string, Change>>>> = {
  'push-up': PUSH_UP,
  'bulgarian-split-squat': SPLIT,
  'pull-up': PULL_UP,
  ...LOADS,
  'calf-raise': CALF,
  'copenhagen-plank': { 'Knee on a chair, bottom foot helping': HELPING },
}
