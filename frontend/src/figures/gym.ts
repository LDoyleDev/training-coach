/**
 * The gym exercises' figures (ADR-0063), by seed slug, grouped by their kit: the barbell and the
 * bench first. Pose keys are as in poses.ts.
 */
import type { Figure } from './poses'

const STAND = { legN: { at: [0, 7] }, legF: { at: [3, 7] } } as const
const CABLE = ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'] as const
/** Standing, seen from in front at chest height (front.ts, perspective.ts). */
const UPRIGHT = { hip: [0, 93.5], tilt: 90, legL: { at: [11, 7] }, legR: { at: [-11, 7] } } as const
const FACING = { at: [0, 125, 330], look: [0, 100, 0] } as const
/** Seated, seen from the front: the thighs coming towards you, the feet on the floor. */
const SEATED = {
  hip: [0, 59],
  tilt: 90,
  legL: { at: [13, 7], mid: [2, -9.1], toward: [43, 40.86] },
  legR: { at: [-13, 7], mid: [-2, -9.1], toward: [43, 40.86] },
} as const

export const GYM: Readonly<Record<string, Figure>> = {
  // ---------------------------------------------------------------- barbell and bench
  'back-squat': {
    frames: [
      'Standing tall, the bar across your upper back',
      'Sitting down between your heels, back flat',
    ],
    view: [-62, 66, -3, 200],
    props: { rack: { x0: -50, x1: 52, pins: 80 }, barbell: true },
    order: ['bell', 'armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1600, 300, 1200, 500],
    start: {
      hip: [5, 93],
      lean: 10,
      ...STAND,
      armN: { at: [-10, 24], from: 'waist', bend: 1 },
      armF: { at: [-9, 24], from: 'waist', bend: 1 },
    },
    end: {
      hip: [-18, 45],
      lean: 40,
      neck: -10,
      ...STAND,
      armN: { at: [-10, 24], from: 'waist', bend: 1 },
      armF: { at: [-9, 24], from: 'waist', bend: 1 },
    },
  },
  'barbell-rdl': {
    frames: [
      'Standing tall, the bar at your thighs, knees soft',
      'Hips back, bar down your legs, back flat',
    ],
    view: [-70, 62, -3, 182],
    props: { barbell: true },
    order: ['bell', 'armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1700, 300, 1200, 500],
    start: {
      hip: [0, 92.5],
      lean: 2,
      ...STAND,
      armN: { dir: -90, reach: 0.995 },
      armF: { dir: -89, reach: 0.995 },
    },
    end: {
      hip: [-28, 87],
      lean: 68,
      neck: -12,
      ...STAND,
      armN: { dir: -96, reach: 0.995 },
      armF: { dir: -95, reach: 0.995 },
    },
  },
  'hip-thrust': {
    frames: [
      'Upper back on the bench, hips low, bar on your hips',
      'Hips up: knees to shoulders in one line',
    ],
    view: [-82, 66, -3, 90],
    props: { bench: { x0: -72, x1: -40, top: 40 }, barbell: true },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
    tempo: [1200, 1000, 1400, 500],
    start: {
      hip: [-6, 22],
      lean: -58,
      neck: 10,
      legN: { at: [40, 7] },
      legF: { at: [43, 7] },
      armN: { at: [13, -16], from: 'waist' },
      armF: { at: [14, -16], from: 'waist' },
    },
    end: {
      hip: [-4, 50],
      lean: -91,
      neck: 22,
      legN: { at: [40, 7] },
      legF: { at: [43, 7] },
      armN: { at: [13, -16], from: 'waist' },
      armF: { at: [14, -16], from: 'waist' },
    },
  },
  'back-extension-45': {
    frames: [
      'Hips on the pad, body in a straight line',
      'Chest lowered towards the floor, back flat',
    ],
    view: [-82, 70, -3, 170],
    props: {
      machine: {
        frame: [
          [-82, 2, 30, 2],
          [-62, 2, -62, 22],
          [4, 2, 4, 70],
          [-62, 20, 4, 70],
        ],
        pads: [
          [-75, 37, -55, 17],
          [4.5, 85.4, -8.7, 70.4],
        ],
        over: [[-63, 50, -63, 50]],
      },
    },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
    tempo: [1500, 300, 1300, 500],
    start: {
      hip: [0, 100],
      lean: 45,
      legN: { at: [-61.4, 38.6], angle: -45 },
      legF: { at: [-59.4, 38.6], angle: -45 },
      armN: { at: [14, 20], from: 'waist' },
      armF: { at: [15, 21], from: 'waist' },
    },
    end: {
      hip: [0, 100],
      lean: 150,
      legN: { at: [-61.4, 38.6], angle: -45 },
      legF: { at: [-59.4, 38.6], angle: -45 },
      armN: { at: [14, 20], from: 'waist' },
      armF: { at: [15, 21], from: 'waist' },
    },
  },
  // ---------------------------------------------------------------- dumbbells and the bench
  'db-bench-press': {
    frames: [
      'On a flat bench, dumbbells pressed up over your chest',
      'Lowered to the sides of your chest',
    ],
    view: [-92, 72, -3, 125],
    props: { incline: { x: 0, top: 44, angle: 180 }, dumbbells: 'across' },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1500, 300, 1100, 500],
    start: {
      hip: [6, 56],
      lean: -90,
      legN: { at: [46, 7] },
      legF: { at: [49, 7] },
      armN: { at: [-35, 111], mid: [1.5, 29.9] },
      armF: { at: [-34, 111], mid: [2, 29.9] },
    },
    end: {
      hip: [6, 56],
      lean: -90,
      legN: { at: [46, 7] },
      legF: { at: [49, 7] },
      armN: { at: [-33, 65], mid: [6, -16] },
      armF: { at: [-32, 65], mid: [6.5, -16] },
    },
  },
  'incline-db-press': {
    frames: ['Bench at about 30°, dumbbells pressed up', 'Lowered to the top of your chest'],
    view: [-92, 80, -3, 150],
    props: { incline: { x: 0, top: 44, angle: 150 }, dumbbells: 'across' },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1500, 300, 1100, 500],
    start: {
      hip: [6, 55],
      lean: -60,
      legN: { at: [52, 7] },
      legF: { at: [55, 7] },
      armN: { at: [-30, 131], mid: [1, 30] },
      armF: { at: [-29, 131], mid: [1.5, 30] },
    },
    end: {
      hip: [6, 55],
      lean: -60,
      legN: { at: [52, 7] },
      legF: { at: [55, 7] },
      armN: { at: [-25, 87], mid: [6, -15] },
      armF: { at: [-24, 87], mid: [6.5, -15] },
    },
  },
  'db-overhead-press': {
    frames: [
      'Sitting tall, back on the pad, dumbbells at your shoulders',
      'Pressed overhead, arms straight',
    ],
    view: [-45, 80, -3, 180],
    props: { incline: { x: 0, top: 44, angle: 95 }, dumbbells: 'across' },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1400, 300, 1200, 500],
    start: {
      hip: [12, 55],
      lean: -5,
      legN: { at: [58, 7] },
      legF: { at: [61, 7] },
      armN: { at: [11, 107], mid: [2, -17] },
      armF: { at: [12, 107], mid: [2.5, -17] },
    },
    end: {
      hip: [12, 55],
      lean: -5,
      legN: { at: [58, 7] },
      legF: { at: [61, 7] },
      armN: { at: [10, 154], mid: [1, 30] },
      armF: { at: [11, 154], mid: [1.5, 30] },
    },
  },
  'incline-db-curl': {
    frames: [
      'Lying back at 45°, arms hanging straight down',
      'Curled up, elbows still under your shoulders',
    ],
    view: [-80, 80, -3, 150],
    props: { incline: { x: 0, top: 44, angle: 135 }, dumbbells: 'across' },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
    tempo: [1100, 400, 2000, 400],
    start: {
      hip: [7, 55],
      lean: -45,
      legN: { at: [54, 7] },
      legF: { at: [57, 7] },
      armN: { at: [-24.1, 30.2], mid: [0, -30] },
      armF: { at: [-23.1, 30.2], mid: [1, -30] },
    },
    end: {
      hip: [7, 55],
      lean: -45,
      legN: { at: [54, 7] },
      legF: { at: [57, 7] },
      armN: { at: [-19.6, 81.5], mid: [0, -30] },
      armF: { at: [-18.6, 81.5], mid: [1, -30] },
    },
  },
  'hammer-curl': {
    frames: [
      'Standing, a dumbbell in each hand, palms facing in',
      'Curled up, the same grip, elbows at your sides',
    ],
    view: [-40, 60, -3, 182],
    props: { dumbbells: 'along' },
    tempo: [1000, 500, 2000, 400],
    start: {
      hip: [0, 93.5],
      lean: 0,
      ...STAND,
      armN: { at: [1.5, 81.54], mid: [0, -30], hand: 0.5 },
      armF: { at: [2.5, 81.54], mid: [1, -30], hand: 0.5 },
    },
    end: {
      hip: [0, 93.5],
      lean: 0,
      ...STAND,
      armN: { at: [13, 130], mid: [0, -30], hand: 0.5 },
      armF: { at: [14, 130], mid: [1, -30], hand: 0.5 },
    },
  },
  'wrist-curl': {
    frames: [
      'Forearms on your thighs, palms up, wrists bent down',
      'Wrists curled up, forearms still',
    ],
    view: [-45, 85, -3, 150],
    props: { incline: { x: -10, top: 44, angle: 180 }, dumbbells: 'across' },
    tempo: [900, 400, 1500, 400],
    start: {
      hip: [0, 55],
      lean: 40,
      legN: { at: [47, 7] },
      legF: { at: [50, 7] },
      armN: { at: [46, 74], angle: -70 },
      armF: { at: [47, 74], angle: -70 },
    },
    end: {
      hip: [0, 55],
      lean: 40,
      legN: { at: [47, 7] },
      legF: { at: [50, 7] },
      armN: { at: [46, 74], angle: 40 },
      armF: { at: [47, 74], angle: 40 },
    },
  },
  'chest-supported-row': {
    frames: ['Chest on an incline bench, arms hanging long', 'Dumbbells pulled to your lower ribs'],
    view: [-45, 90, -3, 135],
    props: { incline: { x: 0, top: 44, angle: 45 }, dumbbells: 'across' },
    tempo: [900, 400, 1400, 400],
    start: {
      hip: [13, 74],
      lean: 45,
      neck: -10,
      legN: { at: [-20, 7] },
      legF: { at: [-17, 7] },
      armN: { at: [39.4, -13.4], from: 'waist' },
      armF: { at: [40, -12.6], from: 'waist' },
    },
    end: {
      hip: [13, 74],
      lean: 45,
      neck: -10,
      legN: { at: [-20, 7] },
      legF: { at: [-17, 7] },
      armN: { at: [12, 8], from: 'waist' },
      armF: { at: [13, 8], from: 'waist' },
    },
  },
  // ---------------------------------------------------------------- machines
  'leg-press': {
    frames: [
      'Back on the pad, feet on the plate, legs nearly straight',
      'Lowered until your knees are well bent',
    ],
    view: [-62, 104, -3, 135],
    props: {
      incline: { x: 0, top: 34, angle: 135 },
      machine: {
        frame: [
          [-10, 2, 98, 2],
          [16, 2, 16, 46],
          [16, 46, 98, 128],
          [98, 2, 98, 128],
        ],
        moves: { on: 'sole' },
      },
    },
    order: ['armF', 'legF', 'torso', 'head', 'armN', 'legN'],
    tempo: [1700, 300, 1300, 500],
    start: {
      hip: [6, 45],
      lean: -45,
      legN: { at: [68.5, 103.5], angle: 135 },
      legF: { at: [71.5, 103.5], angle: 135 },
      armN: { at: [18, 40] },
      armF: { at: [19, 40] },
    },
    end: {
      hip: [6, 45],
      lean: -45,
      legN: { at: [38, 73], angle: 135 },
      legF: { at: [41, 73], angle: 135 },
      armN: { at: [18, 40] },
      armF: { at: [19, 40] },
    },
  },
  'leg-extension': {
    frames: ['Seated, the pad on your shins, knees bent', 'Legs straight, squeeze'],
    view: [-30, 118, -3, 145],
    props: {
      incline: { x: 0, top: 50, angle: 100 },
      machine: { frame: [[56, 2, 56, 61]], moves: { on: 'shin', pivot: [56, 61] } },
    },
    tempo: [900, 500, 1800, 400],
    start: {
      hip: [12, 61],
      lean: -10,
      legN: { at: [50, 19], angle: -10 },
      legF: { at: [53, 19], angle: -10 },
      armN: { at: [24, 52] },
      armF: { at: [25, 52] },
    },
    end: {
      hip: [12, 61],
      lean: -10,
      legN: { at: [98.8, 62], angle: 80 },
      legF: { at: [99.6, 62.5], angle: 80 },
      armN: { at: [24, 52] },
      armF: { at: [25, 52] },
    },
  },
  'seated-leg-curl': {
    frames: ['Legs out straight, the pad above your heels', 'Heels curled under the seat'],
    view: [-30, 118, -3, 145],
    props: {
      incline: { x: 0, top: 50, angle: 105 },
      machine: {
        frame: [[56, 2, 56, 61]],
        over: [[34, 75, 48, 75]],
        moves: { on: 'calf', pivot: [56, 61] },
      },
    },
    tempo: [1000, 400, 1800, 400],
    start: {
      hip: [12, 61],
      lean: -15,
      legN: { at: [98.8, 62], angle: 80 },
      legF: { at: [99.6, 62.5], angle: 80 },
      armN: { at: [24, 52] },
      armF: { at: [25, 52] },
    },
    end: {
      hip: [12, 61],
      lean: -15,
      legN: { at: [44, 20], angle: -20 },
      legF: { at: [47, 20], angle: -20 },
      armN: { at: [24, 52] },
      armF: { at: [25, 52] },
    },
  },
  'standing-calf-raise': {
    frames: [
      'Balls of the feet on the edge, shoulders under the pads, heels down',
      'Up as high as you can',
    ],
    view: [-75, 50, -3, 200],
    props: {
      step: { x0: 0, x1: 34, top: 18 },
      machine: { frame: [[-60, 2, -60, 190]], moves: { on: 'shoulder', pivot: [-60, 150] } },
    },
    tempo: [900, 700, 1300, 400],
    start: {
      hip: [-11.5, 104.4],
      lean: 0,
      legN: { at: [-13.76, 18.08], angle: 28, floor: 18 },
      legF: { at: [-11.75, 18.08], angle: 28, floor: 18 },
      armN: { at: [12, 30], from: 'waist' },
      armF: { at: [13, 30], from: 'waist' },
    },
    end: {
      hip: [-3, 117.8],
      lean: 0,
      legN: { at: [-4.93, 31.52], angle: -38, floor: 18 },
      legF: { at: [-2.875, 31.52], angle: -38, floor: 18 },
      armN: { at: [12, 30], from: 'waist' },
      armF: { at: [13, 30], from: 'waist' },
    },
  },
  'seated-calf-raise': {
    frames: [
      'Seated, the pad on your thighs, heels down off the edge',
      'Heels up as high as you can',
    ],
    view: [-40, 90, -3, 140],
    props: {
      step: { x0: 50, x1: 75, top: 12 },
      machine: {
        frame: [
          [-20, 2, -20, 40],
          [-35, 2, 80, 2],
          [80, 2, 80, 90],
        ],
        pads: [[-30, 40, 8, 40]],
        moves: { on: 'knee', pivot: [80, 80] },
      },
    },
    tempo: [900, 700, 1300, 400],
    start: {
      hip: [0, 56],
      lean: 0,
      legN: { at: [36.24, 12.08], angle: 28, floor: 12 },
      legF: { at: [38.24, 12.08], angle: 28, floor: 12 },
      armN: { at: [30, 3], from: 'waist' },
      armF: { at: [31, 3], from: 'waist' },
    },
    end: {
      hip: [0, 56],
      lean: 0,
      legN: { at: [45.07, 25.52], angle: -38, floor: 12 },
      legF: { at: [47.07, 25.52], angle: -38, floor: 12 },
      armN: { at: [30, 3], from: 'waist' },
      armF: { at: [31, 3], from: 'waist' },
    },
  },
  // ---------------------------------------------------------------- cables
  'lat-pulldown': {
    frames: [
      'Seated, thighs under the pads, arms straight up to the bar',
      'Bar pulled to your upper chest, elbows down and back',
    ],
    view: [-45, 70, -3, 225],
    props: {
      cable: { x: 55, pulley: [4, 214], grip: 'bar' },
      machine: {
        frame: [
          [-8, 2, -8, 44],
          [-25, 2, 55, 2],
        ],
        pads: [[-20, 44, 14, 44]],
        over: [[28, 70, 28, 70]],
      },
    },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
    tempo: [1100, 400, 1600, 400],
    start: {
      hip: [0, 59],
      lean: -12,
      legN: { at: [44, 7] },
      legF: { at: [47, 7] },
      armN: { at: [2, 156], mid: [5.9, 29.4] },
      armF: { at: [3, 156], mid: [6.4, 29.3] },
    },
    end: {
      hip: [0, 59],
      lean: -12,
      legN: { at: [44, 7] },
      legF: { at: [47, 7] },
      armN: { at: [6, 100], mid: [10, -20] },
      armF: { at: [7, 100], mid: [10.5, -20] },
    },
  },
  'overhead-cable-extension': {
    frames: [
      'Facing away from the pulley, elbows by your ears, hands behind your head',
      'Arms straight forward and up',
    ],
    view: [-75, 90, -3, 210],
    props: { cable: { x: -65, pulley: [-60, 185], grip: 'rope' } },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
    tempo: [1100, 400, 1600, 400],
    start: {
      hip: [0, 90],
      lean: 25,
      legN: { at: [24, 7] },
      legF: { at: [-26, 9], angle: 20 },
      armN: { at: [-8, 140] },
      armF: { at: [-7, 140] },
    },
    end: {
      hip: [0, 90],
      lean: 25,
      legN: { at: [24, 7] },
      legF: { at: [-26, 9], angle: 20 },
      armN: { at: [60, 170] },
      armF: { at: [61, 170] },
    },
  },
  'cable-crunch': {
    frames: [
      'Kneeling, the rope held beside your head',
      'Ribs curled towards your hips, back rounded',
    ],
    view: [-62, 85, -3, 215],
    props: { mat: [-60, 40], cable: { x: 75, pulley: [70, 200], grip: 'rope' } },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
    tempo: [1100, 500, 1800, 400],
    start: {
      hip: [0, 49.4],
      lean: 20,
      legN: { at: [-42.5, 11.6], angle: -100 },
      legF: { at: [-40, 11.6], angle: -100 },
      armN: { at: [4, -6], from: 'head' },
      armF: { at: [5, -6], from: 'head' },
    },
    end: {
      hip: [0, 49.4],
      lean: 45,
      spine: 60,
      neck: 20,
      legN: { at: [-42.5, 11.6], angle: -100 },
      legF: { at: [-40, 11.6], angle: -100 },
      armN: { at: [4, -6], from: 'head' },
      armF: { at: [5, -6], from: 'head' },
    },
  },
  'pallof-press': {
    frames: [
      'Side-on to the cable, the handle at your chest',
      "Pressed straight out; hold, don't let it turn you",
    ],
    view: [-40, 75, -3, 182],
    props: { cable: { x: -12, pulley: [-6, 128], grip: 'handle' } },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
    tempo: [1000, 1200, 1000, 500],
    start: {
      hip: [0, 90],
      lean: 0,
      legN: { at: [4, 7] },
      legF: { at: [-4, 7] },
      armN: { at: [18, 118] },
      armF: { at: [19, 118] },
    },
    end: {
      hip: [0, 90],
      lean: 0,
      legN: { at: [4, 7] },
      legF: { at: [-4, 7] },
      armN: { at: [55.8, 127] },
      armF: { at: [56.5, 127] },
    },
  },
  // ---------------------------------------------------------------- sideways, seen from the front
  'cable-lateral-raise': {
    frames: [
      'Side-on to a low pulley, the handle in your far hand',
      'Arm raised out to the side to shoulder height',
    ],
    view: [-40, 60, -3, 182],
    props: { cable: { x: 2, pulley: [6, 15], grip: 'handle' } },
    order: CABLE,
    tempo: [1000, 400, 1800, 400],
    start: {
      hip: [0, 93.5],
      lean: 0,
      ...STAND,
      armN: { at: [4, 82], mid: [1, -30] },
      armF: { at: [4, -2], from: 'waist' },
    },
    end: {
      hip: [0, 93.5],
      lean: 0,
      ...STAND,
      armN: { at: [6, 128], mid: [3, -5] },
      armF: { at: [4, -2], from: 'waist' },
    },
    front: {
      view: [-63, 86, -105, 75],
      camera: FACING,
      standing: true,
      cables: [{ pulley: [-48, 14, 10], hand: 'L' }],
      start: {
        ...UPRIGHT,
        armL: { at: [10, 85], mid: [2, -29.9], toward: [4, 12] },
        armR: { at: [-14, -2], from: 'waist', bend: -1 },
      },
      end: {
        ...UPRIGHT,
        armL: { at: [70, 133], mid: [29, -3], toward: [0, 2] },
        armR: { at: [-14, -2], from: 'waist', bend: -1 },
      },
    },
  },
  'chest-fly': {
    frames: ['Arms wide, a soft bend in the elbows', 'Hands together in front of your chest'],
    view: [-40, 70, -3, 182],
    props: { cable: { x: -4, pulley: [0, 150], grip: 'handle' } },
    order: CABLE,
    tempo: [1200, 400, 1600, 400],
    start: {
      hip: [0, 93.5],
      lean: 0,
      ...STAND,
      armN: { at: [10, 126], mid: [6, -5] },
      armF: { at: [11, 126], mid: [7, -5] },
    },
    end: {
      hip: [0, 93.5],
      lean: 0,
      ...STAND,
      armN: { at: [50, 120], mid: [27, -6] },
      armF: { at: [51, 120], mid: [28, -6] },
    },
    // From the side the arms sweep towards you and away, which reads as a front raise, so the
    // fly is shown from the front only.
    front: {
      only: true,
      view: [-99, 99, -100, 90],
      camera: FACING,
      standing: true,
      cables: [
        { pulley: [88, 150, -6], hand: 'L' },
        { pulley: [-88, 150, -6], hand: 'R' },
      ],
      start: {
        ...UPRIGHT,
        armL: { at: [73, 128], mid: [29.7, -4], toward: [-2, -4] },
        armR: { at: [-73, 128], mid: [-29.7, -4], toward: [-2, -4] },
      },
      end: {
        ...UPRIGHT,
        armL: { at: [6, 120], mid: [10, -9], toward: [26, 50] },
        armR: { at: [-6, 120], mid: [-10, -9], toward: [26, 50] },
      },
    },
  },
  // Seated facing the machine, chest on its pad: a lever from above each shoulder to each hand.
  'reverse-pec-deck': {
    frames: [
      'Seated, chest on the pad, arms out in front at shoulder height, hands together',
      'Opened wide and back, elbows leading',
    ],
    view: [-45, 70, -3, 160],
    props: {
      machine: {
        frame: [
          [-40, 2, 30, 2],
          [-2, 2, -2, 44],
          [18, 2, 18, 75],
          [-35, 2, -35, 150],
          [-35, 150, -4, 150],
        ],
        pads: [
          [-20, 44, 14, 44],
          [18, 75, 18, 98],
        ],
        moves: { on: 'hand', pivot: [-4, 150] },
      },
    },
    tempo: [1100, 500, 1700, 400],
    start: {
      hip: [0, 59],
      lean: 0,
      legN: { at: [40, 7] },
      legF: { at: [43, 7] },
      armN: { at: [54, 102], mid: [30, 0] },
      armF: { at: [55, 102], mid: [30, 0] },
    },
    end: {
      hip: [0, 59],
      lean: 0,
      legN: { at: [40, 7] },
      legF: { at: [43, 7] },
      armN: { at: [-4, 100], mid: [-1, -2] },
      armF: { at: [-3, 100], mid: [-1, -2] },
    },
    front: {
      view: [-83, 83, -101, 83],
      camera: { at: [0, 120, 330], look: [0, 85, 0] },
      standing: true,
      machine: {
        frame: [
          [
            [0, 2, -40],
            [0, 2, 30],
          ],
          [
            [-25, 2, -35],
            [25, 2, -35],
          ],
          [
            [0, 2, -2],
            [0, 44, -2],
          ],
          [
            [0, 2, 18],
            [0, 75, 18],
          ],
          [
            [0, 2, -35],
            [0, 150, -35],
          ],
          [
            [0, 150, -35],
            [0, 150, -4],
          ],
          [
            [-14, 150, -4],
            [14, 150, -4],
          ],
        ],
        pads: [
          [
            [-18, 44, -20],
            [18, 50, 14],
          ],
          [
            [-14, 75, 13.5],
            [14, 98, 22.5],
          ],
        ],
        levers: [
          { pivot: [14, 150, -4], hand: 'L' },
          { pivot: [-14, 150, -4], hand: 'R' },
        ],
      },
      start: {
        ...SEATED,
        armL: { at: [5, 102], mid: [6, -1], toward: [28, 52] },
        armR: { at: [-5, 102], mid: [-6, -1], toward: [28, 52] },
      },
      end: {
        ...SEATED,
        armL: { at: [73, 102], mid: [30, 0], toward: [-4, -8] },
        armR: { at: [-73, 102], mid: [-30, 0], toward: [-4, -8] },
      },
    },
  },
}
