/**
 * The entry exercises' figures for the upper body, bands and the seated and standing adductor
 * and hamstring moves (ADR-0083, #507), by seed slug, and the ladder steps that change them
 * (ADR-0063, addendum). Pose keys are as in poses.ts.
 */
import { BODY, type Vec } from './body'
import type { FrontLimb, FrontPose } from './front'
import type { Bench3, Camera } from './perspective'
import type { Figure } from './poses'

const STAND = { legN: { at: [0, 7] }, legF: { at: [3, 7] } } as const
/** Seated on a chair, feet flat in front. */
const SIT_FEET = { legN: { at: [40, 7] }, legF: { at: [43, 7] } } as const
const BAND_ORDER = ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'] as const
/** A kitchen chair seen side on, its back behind you, the seat 45 cm high. */
const CHAIR = { x0: -34, x1: 12, seat: 45 }
/** A kitchen counter in front of you, its edge at ``x``, 90 cm high. */
const counter = (x: number) => ({ x0: x, x1: x + 30, top: 90 })

// ---------------------------------------------------------------- from the front
/** Seen from in front of a seated figure, a little above the shoulders. */
const SEATED_CAMERA: Camera = { at: [0, 120, 330], look: [0, 85, 0] }
const FACING: Camera = { at: [0, 125, 330], look: [0, 100, 0] }
/** A chair's seat seen in the round. */
const SEAT: Bench3 = { x0: -24, x1: 24, top: 45, depth: 42 }
const SEAT_HIP = 56

/** The left leg seated, seen from the front: the knee at ``knee`` (x, height) and the ankle at
 * ``ankle`` across, the thigh and shin coming towards you as far as their lengths allow. The right
 * leg mirrors it. */
function seatedLegs(knee: Vec, ankle: number): Pick<FrontPose, 'legL' | 'legR'> {
  const root = 9 // the hip joint, out from the middle
  const kz = Math.sqrt(BODY.thigh ** 2 - (knee[0] - root) ** 2 - (knee[1] - SEAT_HIP) ** 2)
  const az = kz - Math.sqrt(BODY.shin ** 2 - (ankle - knee[0]) ** 2 - (knee[1] - 7) ** 2)
  const leg = (s: number): FrontLimb => ({
    at: [s * ankle, 7],
    mid: [s * (knee[0] - root), knee[1] - SEAT_HIP],
    toward: [kz, az],
  })
  return { legL: leg(1), legR: leg(-1) }
}

/** Hands holding the sides of the seat. */
const HOLD_SEAT = {
  armL: { at: [27, 49] },
  armR: { at: [-27, 49], bend: -1 },
} as const

// ---------------------------------------------------------------- the figures
export const ENTRY_UPPER: Readonly<Record<string, Figure>> = {
  // Hands on the armrests by the hips; pushing down lifts the hips off the seat.
  'armchair-press-up': {
    frames: [
      'Sitting in an armchair, hands on the armrests by your hips',
      'Arms straight, hips lifted off the seat, shoulders down',
    ],
    view: [-48, 70, -3, 175],
    props: { armchair: { x0: -40, x1: 20 } },
    tempo: [1300, 500, 1600, 500],
    start: {
      hip: [-6, 56],
      lean: 8,
      legN: { at: [38, 7] },
      legF: { at: [41, 7] },
      armN: { at: [6, 66], angle: 0 },
      armF: { at: [7, 66], angle: 0 },
    },
    end: {
      hip: [-4, 76],
      lean: 6,
      legN: { at: [38, 7] },
      legF: { at: [41, 7] },
      armN: { at: [6, 66], angle: 0 },
      armF: { at: [7, 66], angle: 0 },
    },
  },
  // Elbows pinned at your sides; the band comes down over the top of the door in front.
  'band-pushdown': {
    frames: [
      'Facing the door, elbows at your sides, hands at chest height',
      'Pushed down until the arms are straight, elbows still at your sides',
    ],
    view: [-40, 70, -3, 203],
    props: { band: { from: [54, 200], to: 'hands', on: 'door' } },
    order: BAND_ORDER,
    tempo: [1000, 400, 1600, 400],
    start: {
      hip: [0, 93.5],
      lean: 6,
      ...STAND,
      armN: { mid: [0, -30], turn: 32 },
      armF: { mid: [1, -30], turn: 32 },
    },
    end: {
      hip: [0, 93.5],
      lean: 6,
      ...STAND,
      armN: { mid: [0, -30], turn: -78 },
      armF: { mid: [1, -30], turn: -78 },
    },
  },
  // Seated, the band shut in a door at chest height in front.
  'band-row': {
    frames: [
      'Sitting tall, arms straight out to the band at chest height',
      'Hands pulled to your ribs, shoulder blades squeezed together',
    ],
    view: [-40, 100, -3, 203],
    props: { chair: CHAIR, band: { from: [92, 96], to: 'hands', on: 'door' } },
    order: BAND_ORDER,
    tempo: [1000, 500, 1600, 400],
    start: {
      hip: [-6, 56],
      lean: 0,
      ...SIT_FEET,
      armN: { at: [47, 96], angle: 0 },
      armF: { at: [48, 96], angle: 0 },
    },
    end: {
      hip: [-6, 56],
      lean: -4,
      ...SIT_FEET,
      armN: { at: [12, 84], angle: 0 },
      armF: { at: [13, 84], angle: 0 },
    },
  },
  // The arms sweep out to the sides, which from the side reads as a front raise, so it is seen
  // from the front only, sitting on a chair as the first step's cue allows.
  'band-pull-apart': {
    frames: [
      'Sitting tall, arms straight out in front at shoulder height, the band between your hands',
      'Hands pulled out to the sides, band to the chest, shoulder blades squeezed',
    ],
    view: [-45, 70, -3, 160],
    props: { chair: CHAIR },
    tempo: [1000, 500, 1500, 400],
    start: {
      hip: [-6, 56],
      lean: 0,
      ...SIT_FEET,
      armN: { at: [48, 98], mid: [30, 0] },
      armF: { at: [49, 98], mid: [30, 0] },
    },
    end: {
      hip: [-6, 56],
      lean: 0,
      ...SIT_FEET,
      armN: { at: [-5, 96], mid: [-1, -2] },
      armF: { at: [-4, 96], mid: [-1, -2] },
    },
    front: {
      only: true,
      view: [-88, 88, -101, 83],
      camera: SEATED_CAMERA,
      seat: SEAT,
      standing: true,
      band: { to: 'hands' },
      start: {
        hip: [0, SEAT_HIP],
        tilt: 90,
        ...seatedLegs([14, 49], 14),
        armL: { at: [15, 96], mid: [-1, -1.5], toward: [29.9, 55.8] },
        armR: { at: [-15, 96], mid: [1, -1.5], toward: [29.9, 55.8] },
      },
      end: {
        hip: [0, SEAT_HIP],
        tilt: 90,
        ...seatedLegs([14, 49], 14),
        armL: { at: [70, 93], mid: [29.4, -3], toward: [3, 9] },
        armR: { at: [-70, 93], mid: [-29.4, -3], toward: [3, 9] },
      },
    },
  },
  // Seated facing a door, the band from its top; elbows pulled down to the sides.
  'band-pulldown': {
    frames: [
      'Sitting facing the door, arms up to the band',
      'Elbows pulled down to your sides, chest up',
    ],
    view: [-45, 76, -3, 203],
    props: { chair: CHAIR, band: { from: [64, 200], to: 'hands', on: 'door' } },
    order: BAND_ORDER,
    tempo: [1100, 400, 1600, 400],
    start: {
      hip: [-6, 56],
      lean: -8,
      ...SIT_FEET,
      armN: { at: [7.4, 151], mid: [5.9, 29.4] },
      armF: { at: [7.9, 150.8], mid: [6.4, 29.3] },
    },
    end: {
      hip: [-6, 56],
      lean: -10,
      spine: -4,
      ...SIT_FEET,
      armN: { at: [8, 100], mid: [9, -20] },
      armF: { at: [9, 100], mid: [9.5, -20] },
    },
  },
  // Seated, a small water bottle in each hand at the shoulders, pressed overhead.
  'seated-press': {
    frames: [
      'Sitting tall, a water bottle in each hand at your shoulders',
      'Pressed overhead, arms straight, back not arched',
    ],
    view: [-45, 70, -3, 190],
    props: { chair: CHAIR, bottles: true },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1300, 300, 1400, 500],
    start: {
      hip: [-6, 56],
      lean: -3,
      ...SIT_FEET,
      armN: { at: [-3, 103], mid: [2, -17] },
      armF: { at: [-2, 103], mid: [2.5, -17] },
    },
    end: {
      hip: [-6, 56],
      lean: -3,
      ...SIT_FEET,
      armN: { at: [-6, 155], mid: [1, 30] },
      armF: { at: [-5, 155], mid: [1.5, 30] },
    },
  },
  // Knees squeezing a folded pillow: seen from the front, as the side view can't show it.
  'adductor-squeeze': {
    frames: [
      'Sitting tall, a folded pillow between your knees',
      'Knees squeezed together into the pillow; hold, breathing',
    ],
    view: [-45, 70, -3, 160],
    props: { chair: CHAIR },
    tempo: [1200, 2400, 1200, 600],
    start: {
      hip: [-6, 56],
      lean: 0,
      ...SIT_FEET,
      armN: { at: [-6, 50] },
      armF: { at: [-5, 50] },
    },
    end: {
      hip: [-6, 56],
      lean: 0,
      ...SIT_FEET,
      armN: { at: [-6, 50] },
      armF: { at: [-5, 50] },
    },
    front: {
      only: true,
      view: [-70, 70, -101, 83],
      camera: SEATED_CAMERA,
      seat: SEAT,
      standing: true,
      pillow: true,
      start: { hip: [0, SEAT_HIP], tilt: 90, ...seatedLegs([15, 49], 16), ...HOLD_SEAT },
      end: { hip: [0, SEAT_HIP], tilt: 90, ...seatedLegs([12, 49], 14), ...HOLD_SEAT },
    },
  },
  // Facing the counter, hands on it; one heel curls up behind, the knees side by side.
  'standing-leg-curl': {
    frames: [
      'Standing tall, hands on the counter',
      'One heel curled up behind you, knees side by side',
    ],
    view: [-62, 74, -3, 182],
    props: { wall: counter(40) },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1100, 400, 1500, 500],
    start: {
      hip: [2, 93.9],
      lean: 10,
      legN: { mid: [0, -44], turn: -90 },
      legF: { at: [3, 7] },
      armN: { at: [41, 92] },
      armF: { at: [43, 92] },
    },
    end: {
      hip: [2, 93.9],
      lean: 10,
      legN: { mid: [0, -44], turn: -195, angle: -60 }, // back round, not forward
      legF: { at: [3, 7] },
      armN: { at: [41, 92] },
      armF: { at: [43, 92] },
    },
  },
}

// ---------------------------------------------------------------- the steps that change them
/** Standing band adduction from the front: a heavy table on your right, the band from its leg
 * round the right ankle, a hand on the counter on your left. The right leg, nearer you, swings
 * straight from the hip from out to the side to across in front of the left. */
const TABLE_LEG: readonly [number, number, number] = [-52, 9, 16]
const ADDUCT_HIP: Vec = [0, 93.5]
const ADDUCTION: Partial<Figure> = {
  frames: [
    'Standing, the band from a table leg round the near ankle, that leg out to the side',
    'The leg swept across in front of the other, hips square',
  ],
  tempo: [1100, 400, 1500, 500],
  front: {
    only: true,
    view: [-104, 100, -110, 92],
    camera: FACING,
    seat: { x0: -92, x1: -48, top: 72, depth: 40 },
    standing: true,
    band: { from: TABLE_LEG, to: 'ankleR' },
    machine: {
      pads: [
        [
          [44, 0, -40],
          [84, 90, 26],
        ],
      ],
    },
    start: {
      hip: ADDUCT_HIP,
      tilt: 90,
      legL: { at: [11, 7] },
      legR: { swing: { dir: -108, toward: 4 } },
      armL: { at: [47, 92] },
      armR: { at: [-23, 83], bend: -1 },
    },
    end: {
      hip: ADDUCT_HIP,
      tilt: 90,
      legL: { at: [11, 7] },
      legR: { swing: { dir: -76, toward: 18 } },
      armL: { at: [47, 92] },
      armR: { at: [-23, 83], bend: -1 },
    },
  },
}

/** The hamstring curl with a band from a table leg in front, round the working ankle. */
const LEG_CURL_BAND: Partial<Figure> = {
  frames: [
    'Hands on the counter, the band from a table leg in front round one ankle',
    'Heel curled up behind against the band, the thigh still',
  ],
  props: {
    wall: counter(40),
    band: { from: [30, 9], to: 'ankle', on: 'table' },
  },
  order: BAND_ORDER,
}

/** The seated press with one 8 kg bell, resting on the back of the forearm; the free hand on the
 * thigh. */
const press = ENTRY_UPPER['seated-press']
const ONE_ARM_PRESS: Partial<Figure> = {
  frames: [
    'Sitting tall, the bell at your shoulder, the free hand on your thigh',
    'Pressed overhead, arm straight, back not arched',
  ],
  props: { chair: CHAIR, bell: 'near' },
  order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN', 'bell'],
  start: { ...press.start, armF: { at: [18, 62] } },
  end: { ...press.end, armF: { at: [18, 62] } },
}

export const ENTRY_UPPER_STEPS: Readonly<
  Record<string, Readonly<Record<string, Partial<Figure>>>>
> = {
  'adductor-squeeze': {
    'Standing band adduction, light band': ADDUCTION,
    'Standing band adduction, medium band': ADDUCTION,
  },
  'standing-leg-curl': { 'Light band': LEG_CURL_BAND, 'Medium band': LEG_CURL_BAND },
  'seated-press': { '8 kg, one arm at a time': ONE_ARM_PRESS },
}
