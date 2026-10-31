/**
 * Ladder steps that change how an exercise is set up (ADR-0063, addendum): a load on the back,
 * a bell in each hand, dip bars in place of chairs. Keyed by slug, then by the step's name as
 * plan.toml writes it; each entry says what changes over the exercise's figure. Every other step
 * shows the figure as it is.
 */
import { BODY, solve, type Pose, type Vec } from './body'
import { FIGURES, type Figure } from './poses'

type Change = Partial<Figure>

/** The same change for several steps. */
const each = (names: readonly string[], change: Change) =>
  Object.fromEntries(names.map((name) => [name, change]))

const LOADED = (steps: readonly string[], figure: Figure) =>
  each(steps, { props: { ...figure.props, load: true } })

/** Hands turned thumbs up round an upright handle: seen from the side, a fist. */
const fist = (pose: Pose): Pose => ({
  ...pose,
  armN: { ...pose.armN, hand: 0.5 },
  armF: { ...pose.armF, hand: 0.5 },
})

const VEST = ['Vest or backpack']

/** A kettlebell held by the horns at the chest, elbows down in front of the ribs: the same
 * movement, the hands placed on the trunk so they ride with it, ``at`` from the waist. */
const goblet = (figure: Figure, frames: Figure['frames'], at: Vec = [19, 21]): Change => {
  const arms = {
    armN: { at, from: 'waist', hand: 0.5 },
    armF: { at: [at[0] + 1, at[1] + 0.5], from: 'waist', hand: 0.5 },
  } as const
  return {
    frames,
    props: { ...figure.props, bell: 'goblet' },
    order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
    start: { ...figure.start, ...arms },
    end: { ...figure.end, ...arms },
  }
}

/** The far leg held up straight, off the floor, at ``angle`` degrees: a single-leg curl. */
const raised = (pose: Pose, angle: number): Pose => {
  const [x, y] = pose.hip ?? [0, 0]
  const reach = 90 // past the leg's length, so it points there, straight
  const at = [
    x + reach * Math.cos((angle * Math.PI) / 180),
    y + reach * Math.sin((angle * Math.PI) / 180),
  ] as const
  return { ...pose, legF: { at, angle: angle + 81 } } // the foot flexed, as on the towel
}

/** Dips with the feet off the floor: between two chairs, one each side, seen as one chair under
 * the hands, its back in front of you; knees bent about square behind you, feet up. The seats are
 * 50 cm high, so at the bottom, upper arms nearly level, the knees are still well off the floor. */
const OFF_FLOOR: Change = {
  frames: [
    'Hands on two chairs, one each side, arms straight, feet tucked up behind',
    'Down until the upper arms are nearly level, knees and feet off the floor',
  ],
  view: [-88, 48, -3, 148],
  props: { chair: { x0: 40, x1: -6, seat: 50, beside: true } },
  start: {
    hip: [-3.1, 65.7],
    lean: 8,
    legN: { at: [-55.4, 45.9], angle: 178 },
    legF: { at: [-52.4, 45.9], angle: 176 },
    armN: { at: [0, 53.4], angle: 0 },
    armF: { at: [0, 53.4], angle: 0 },
  },
  end: {
    hip: [-8, 50.9],
    lean: 30,
    legN: { at: [-63.8, 55], angle: 172 },
    legF: { at: [-60.8, 55], angle: 170 },
    armN: { at: [0, 53.4], angle: 0 },
    armF: { at: [0, 53.4], angle: 0 },
  },
}
const OFF_FLOOR_LOADED: Change = { ...OFF_FLOOR, props: { ...OFF_FLOOR.props, load: true } }

/** A Nordic curl: kneeling tall, heels hooked under the front of a sofa, the body falling forward
 * in one line from the knees, the hamstrings braking it. The knees and feet are the reverse
 * Nordic's. The knees are at the sofa's front, so the sofa takes little width and the figure is
 * drawn as big as a reverse Nordic. */
const NORDIC_LEGS = {
  legN: { at: [-42.5, 11.6], angle: -100 },
  legF: { at: [-42.5, 11.6], angle: -100 },
} as const
const nordic = (frames: Figure['frames'], hands: Vec, tempo: Figure['tempo']): Change => ({
  frames,
  view: [-60, 118, -3, 131],
  props: { mat: [-50, 116], sofa: { x0: -58, x1: -8 } },
  tempo,
  start: {
    kneel: { knee: [0.1, 5.4], angle: 90 },
    lean: 0,
    ...NORDIC_LEGS,
    armN: { at: [12, 22], from: 'waist' },
    armF: { at: [13, 22], from: 'waist' },
  },
  end: {
    kneel: { knee: [0.1, 5.4], angle: 18 },
    lean: 0,
    neck: -8,
    ...NORDIC_LEGS,
    armN: { at: hands, from: 'waist', angle: 0 },
    armF: { at: [hands[0], hands[1] + 1.5], from: 'waist', angle: 0 },
  },
})

/** A pistol sitting down to a seat behind: on one leg, the other held out in front, down until
 * the seat takes your weight, hips at ``hip``, the free leg pointing ``dir`` degrees. */
const sitTo = (frames: Figure['frames'], hip: Vec, lean: number, dir: number): Change => {
  const pistol = FIGURES['pistol-squat']
  const free = (d: number): Vec => [
    hip[0] + 90 * Math.cos((d * Math.PI) / 180),
    hip[1] + 90 * Math.sin((d * Math.PI) / 180),
  ]
  return {
    frames,
    view: [-82, 100, -3, 175],
    start: pistol.start,
    end: {
      hip,
      lean,
      neck: -6,
      legN: { at: [0, 7] },
      legF: { at: free(dir), angle: dir + 80 },
      armN: { dir: -4, reach: 0.995 },
      armF: { dir: -2, reach: 0.995 },
    },
  }
}

/** A one-arm swing: the bell in the near hand, the free hand hanging at your side. */
const ONE_ARM: Change = {
  frames: ['Hinge, the bell in one hand behind the knees', 'Stand tall, bell at chest height'],
  props: { bell: 'one' },
  start: {
    ...FIGURES['kb-swing'].start,
    armF: { dir: -100, reach: 0.995 },
  },
  end: {
    ...FIGURES['kb-swing'].end,
    armF: { dir: -95, reach: 0.995 },
  },
}

/** Tibialis raises a step further from the wall: the heels 12 cm further out, the hips lower. */
const tibialis = FIGURES['tibialis-raise']
const further = (pose: Pose): Pose => ({
  ...pose,
  hip: [-27, 85],
  lean: -7,
  legN: { ...pose.legN, at: [12, 7.3] },
  legF: { ...pose.legF, at: [15, 7.3] },
})

/** A Copenhagen plank with the top ankle on the chair: the top leg straight, a longer lever, the
 * chair further away. As in the figure, the shoulder stays over the bottom elbow; low, the hips
 * drop; up, ankle to shoulder in one line, seen from the side and from the front. */
const copenhagen = FIGURES['copenhagen-plank']
const ANKLE_ON_CHAIR: Change = {
  frames: [
    'On your side, top ankle on a chair, top leg straight, hips low',
    'Hips up until the body is straight, ankle to shoulder',
  ],
  view: [-162, 35, -3, 95],
  props: { bench: { x0: -158, x1: -110, top: 46 } },
  start: {
    ...copenhagen.start,
    legN: { at: [-124, 51], angle: 180, bend: -1 },
  },
  end: {
    ...copenhagen.end,
    hip: [-43.63, 39.68],
    lean: 97.45,
    legN: { at: [-130, 51], angle: 180, bend: -1 },
  },
  front: copenhagen.front && {
    ...copenhagen.front,
    view: [-90, 82, -62, 72],
    seat: { x0: -160, x1: -116, top: 46, depth: 40 },
    start: { ...copenhagen.front.start, legR: { at: [-133, 52], bend: -1 } },
    end: {
      ...copenhagen.front.end,
      hip: [-45.2, 49.2],
      tilt: 4,
      legR: { at: [-132.6, 52.1], bend: -1 },
    },
  },
}

/** A reverse Nordic leaning further back than the figure: the thighs ``angle`` degrees from the
 * floor in front (90 upright), knees to head in one line, pivoting on the knees; the hands at
 * ``hands`` from the waist at the bottom. Its picture runs from ``x0`` to well in front of the
 * knees, wide enough for its two positions to go one above the other at full width. */
const reverse = FIGURES['reverse-nordic']
const KNEEL_F = { at: [-42, 11.6], angle: -100 } as const // the far knee stays down with the near
const leanBack = (frames: Figure['frames'], angle: number, hands: Vec, x0: number): Change => ({
  frames,
  view: [x0, x0 + 175, -3, 131],
  start: {
    ...reverse.start,
    hip: undefined,
    kneel: { knee: [0.1, 5.4], angle: 90 },
    legF: KNEEL_F,
  },
  end: {
    ...reverse.end,
    hip: undefined,
    kneel: { knee: [0.1, 5.4], angle },
    lean: 0,
    legF: KNEEL_F,
    armN: { at: hands, from: 'waist' },
    armF: { at: [hands[0] + 1, hands[1]], from: 'waist' },
  },
})

/** A push-up's plank with the balls of the feet at ``ball`` and the body line at ``start`` and
 * ``end`` degrees, the hands where the figure has them unless ``hands`` moves them. */
const plank = (
  figure: Figure,
  ball: Vec,
  [start, end]: readonly [number, number],
  hands?: Vec,
): Pick<Figure, 'start' | 'end'> => {
  const arms = (pose: Pose): Pose =>
    hands
      ? {
          ...pose,
          armN: { ...pose.armN, at: hands },
          armF: { ...pose.armF, at: [hands[0] + 2.7, hands[1]] },
        }
      : pose
  return {
    start: arms({ ...figure.start, plank: { ball, angle: start } }),
    end: arms({ ...figure.end, plank: { ball, angle: end } }),
  }
}

/** Feet on a chair behind you: the body slopes down to the hands. */
const ON_CHAIR = { chair: { x0: -62, x1: -6, seat: 45 } }
const push = FIGURES['push-up']
const diamond = FIGURES['diamond-push-up']

/** An archer push-up seen from the side: the far arm bends as in a push-up; the near one stays
 * straight, out to the side towards you, so it is drawn short, in front of the body, its elbow
 * on the line from the shoulder to the hand. */
const straightOut = (pose: Pose): Pose => {
  const j = solve(pose)
  const [dx, dy] = [j.armN.wrist[0] - j.shoulder[0], j.armN.wrist[1] - j.shoulder[1]]
  const share = BODY.upperArm / (BODY.upperArm + BODY.forearm)
  return { ...pose, armN: { ...pose.armN, mid: [dx * share, dy * share] } }
}

/** The archer seen from in front of the head, where the straight arm reads (front.ts, laid face
 * down): hands wide, both arms straight; then down over the right arm as it bends, the body
 * shifting towards it, the left arm straight out to the side. The hands stay put on the floor. */
const ARCHER: Figure['front'] = {
  view: [-85, 79, -83, 79],
  camera: { at: [0, 230, 330], look: [0, 15, 75] },
  standing: true,
  start: {
    hip: [0, 100],
    tilt: 90,
    lie: { slope: 13.3, lift: 10.89 },
    legL: { at: [10, 13.1] },
    legR: { at: [-10, 13.1] },
    armL: { at: [55, 144], mid: [19.82, 0], toward: [22.52, 42.04] },
    armR: { at: [-55, 144], mid: [-19.82, 0], toward: [22.52, 42.04] },
  },
  end: {
    hip: [-14.94, 100],
    tilt: 90,
    lie: { slope: 4, lift: 13.06 },
    legL: { at: [2, 14] },
    legR: { at: [-16, 14] },
    armL: { at: [55, 148.75], mid: [27.82, 2.54], toward: [10.92, 20.38] },
    armR: { at: [-55, 148.75], mid: [-29.75, 0], toward: [-3.9, 20.38] },
  },
}

/** A pike push-up with the feet on a chair: hips over the shoulders, nearly upside down. */
const pike = FIGURES['pike-push-up']
const PIKE_FEET = {
  legN: { at: [-24, 59.1], angle: -45, floor: 45 },
  legF: { at: [-21, 59.1], angle: -45, floor: 45 },
} as const

/** Upside down against a wall, back to it: hands on the floor, heels on the wall. */
const handstand = (shoulder: number, lean: number): Pose => {
  const hip: Vec = [6, shoulder + 44]
  return {
    hip,
    lean,
    legN: { at: [9, hip[1] + 86.5], angle: 95 },
    legF: { at: [11, hip[1] + 86.5], angle: 95 },
    armN: { at: [-2, 3], angle: 180 },
    armF: { at: [0, 3], angle: 180 },
  }
}

/** On dip bars: hands on the bars, knees bent, leaning a little forward at the bottom. */
const BARS: Change = {
  frames: ['Arms straight on the bars, knees bent', 'Leaning slightly forward, elbows back'],
  view: [-60, 70, -3, 230],
  props: { bars: { x: 0, top: 120 } },
  start: {
    hip: [-3.1, 135.9],
    lean: 8,
    legN: { at: [-30, 76], angle: -60 },
    legF: { at: [-27, 76], angle: -62 },
    armN: { at: [0, 123.5], angle: 0 },
    armF: { at: [0, 123.5], angle: 0 },
  },
  end: {
    hip: [-1, 108.7],
    lean: 20,
    legN: { at: [-30, 48], angle: -60 },
    legF: { at: [-27, 48], angle: -62 },
    armN: { at: [0, 123.5], angle: 0 },
    armF: { at: [0, 123.5], angle: 0 },
  },
}

/** A kitchen counter in front of you, its edge at ``x``, 90 cm high (ADR-0083's entry steps). */
const counter = (x: number) => ({ wall: { x0: x, x1: x + 30, top: 90 } })

/** Glute bridge, standing at the counter: both hands on it, one straight leg taken back from the
 * hip and squeezed, the other leg standing (the off-floor first step, ADR-0083). */
const STANDING_BRIDGE: Change = {
  frames: [
    'Hands on the counter, standing on both feet',
    'One straight leg taken back, glute squeezed',
  ],
  view: [-58, 74, -3, 182],
  props: counter(40),
  order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
  tempo: [1300, 1000, 1300, 500],
  ease: 'sine',
  start: {
    hip: [0, 92.5],
    lean: 12,
    legN: { at: [1, 7] },
    legF: { at: [3, 7] },
    armN: { at: [41, 92] },
    armF: { at: [43, 92] },
  },
  end: {
    hip: [0, 92.5],
    lean: 16,
    legN: { at: [-30.2, 11], angle: -20 },
    legF: { at: [3, 7] },
    armN: { at: [41, 92] },
    armF: { at: [43, 92] },
  },
}

/** A hip thrust with the shoulders on the sofa's front edge, hands on the hips. */
const SOFA_THRUST: Change = {
  frames: ['Upper back on the sofa, hips low', 'Hips up: knees to shoulders in one line'],
  view: [-124, 68, -3, 100],
  props: { sofa: { x0: -120, x1: -38 } },
  order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN'],
  tempo: [1200, 1000, 1400, 500],
  start: {
    hip: [-6, 26],
    lean: -58,
    neck: 10,
    legN: { at: [40, 7] },
    legF: { at: [43, 7] },
    armN: { at: [13, -16], from: 'waist' },
    armF: { at: [14, -16], from: 'waist' },
  },
  end: {
    hip: [-4, 54],
    lean: -91,
    neck: 22,
    legN: { at: [40, 7] },
    legF: { at: [43, 7] },
    armN: { at: [13, -16], from: 'waist' },
    armF: { at: [14, -16], from: 'waist' },
  },
}

/** The same bridge on one leg: the far leg held up straight, in line with the near thigh. */
const oneLeg = (change: Change, frames: Figure['frames'], up: number): Change => ({
  ...change,
  frames,
  view: [change.view![0], change.view![1] + 20, -3, change.view![3] + up],
  start: raised(change.start!, 38),
  end: raised(change.end!, 30),
})

/** A hip hinge with the hands on the counter's edge: from a slight bend, hips back until arms and
 * back make one line. */
const COUNTER_HINGE: Change = {
  frames: [
    'Hands on the counter, a slight bend at the hips',
    'Hips back: arms and back in one line',
  ],
  view: [-60, 96, -3, 182],
  props: counter(62),
  start: {
    hip: [-10, 90],
    lean: 40,
    legN: { at: [0, 7] },
    legF: { at: [3, 7] },
    armN: { at: [64, 92] },
    armF: { at: [66, 92] },
  },
  end: {
    hip: [-35, 88],
    lean: 82,
    neck: -6,
    legN: { at: [0, 7] },
    legF: { at: [3, 7] },
    armN: { at: [64, 92] },
    armF: { at: [66, 92] },
  },
}

/** A bag hugged to the chest through the hinge, the hands on the trunk so they ride with it. */
const hugged = (pose: Pose): Pose => ({
  ...pose,
  armN: { at: [19, 20], from: 'waist' },
  armF: { at: [20, 20.5], from: 'waist' },
})

export const STEPS: Readonly<Record<string, Readonly<Record<string, Change>>>> = {
  'pull-up': LOADED(VEST, FIGURES['pull-up']),
  'chin-up': LOADED(VEST, FIGURES['chin-up']),
  dip: {
    'Feet off floor': OFF_FLOOR,
    ...each(['Feet off floor, 5 kg vest or backpack', 'Feet off floor, 10 kg'], OFF_FLOOR_LOADED),
    'Dip bars, bodyweight, full range': BARS,
    'Dip bars, vest or backpack': { ...BARS, props: { ...BARS.props, load: true } },
  },
  'bulgarian-split-squat': {
    ...each(
      [
        'Goblet hold, 8 kg',
        'Goblet hold, 3 s lowering',
        'Goblet hold, 16 kg',
        'Goblet hold 16 kg, 3 s lowering',
      ],
      goblet(FIGURES['bulgarian-split-squat'], [
        'Tall, a bell held at your chest by the horns',
        'Back knee just above the floor, bell still at your chest',
      ]),
    ),
    'Suitcase hold, 16 kg + 8 kg': {
      frames: ['Tall, a bell in each hand at your sides', 'Back knee just above the floor'],
      props: { ...FIGURES['bulgarian-split-squat'].props, bell: 'sides' },
      order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN', 'bell'],
      start: {
        ...FIGURES['bulgarian-split-squat'].start,
        armN: { dir: -87, reach: 0.995 },
        armF: { dir: -100, reach: 0.995 },
      },
      end: {
        ...FIGURES['bulgarian-split-squat'].end,
        armN: { dir: -87, reach: 0.995 },
        armF: { dir: -100, reach: 0.995 },
      },
    },
  },
  'hamstring-curl': {
    'Towel slide, single leg': {
      frames: [
        'Hips up, one heel on the towel, the other leg held up straight',
        'Heel pulled to your glutes, the other leg still up',
      ],
      view: [-82, 100, -3, 108],
      start: raised(FIGURES['hamstring-curl'].start, 35),
      end: raised(FIGURES['hamstring-curl'].end, 35),
    },
    'Nordic curl negatives': nordic(
      ['Kneeling tall, heels hooked under a sofa', 'Lowered as slowly as you can, hands catch you'],
      [30.7, 24.7],
      [3000, 300, 900, 500],
    ),
    'Full Nordic curl': nordic(
      [
        'Kneeling tall, heels hooked under a sofa',
        'Lowered as far as you can, then pulled back up by the hamstrings',
      ],
      [22, 22],
      [2600, 300, 2600, 500],
    ),
  },
  'tibialis-raise': {
    'Heels further from wall': {
      frames: ['Back against a wall, heels further out', 'Toes up as high as you can'],
      start: further(tibialis.start),
      end: further(tibialis.end),
    },
    'Single leg': {
      frames: ['On one heel, the other foot lifted', 'Toes up as high as you can'],
      start: { ...tibialis.start, legF: { at: [10, 30], angle: 10 } },
      end: { ...tibialis.end, legF: { at: [10, 30], angle: 10 } },
    },
    'Holding 8 kg on toes': {
      frames: ['A bell resting on your toes', 'Toes up as high as you can, lifting it'],
      props: { ...tibialis.props, bell: 'toes' },
      order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN', 'bell'],
    },
  },
  'jump-squat': {
    'Holding 8 kg': goblet(FIGURES['jump-squat'], [
      'Squat to about parallel, a bell held at your chest',
      'Jump, legs straight, the bell still at your chest',
    ]),
  },
  'kb-swing': { 'One-arm, 8 kg': ONE_ARM, 'One-arm, 16 kg': ONE_ARM },
  'pistol-squat': {
    'Sit to chair on one leg': {
      ...sitTo(
        ['On one leg, a chair behind you', 'Sat down on the chair, the other leg still out'],
        [-30, 56],
        32,
        -12,
      ),
      props: { chair: { x0: -80, x1: -32, seat: 45 } },
    },
    'Lower box': {
      ...sitTo(
        ['On one leg, a low box behind you', 'Sat down on the box, the other leg still out'],
        [-24, 41],
        40,
        -4,
      ),
      props: { step: { x0: -66, x1: -26, top: 32 } },
    },
    // Held further out, as a counterweight, above the free leg.
    'Holding 8 kg': goblet(
      FIGURES['pistol-squat'],
      [
        'On one leg, a bell held out in front of your chest',
        'All the way down, the bell still out in front',
      ],
      [30, 34],
    ),
  },
  'calf-raise': {
    ...each(['Holding 8 kg', '8 kg, 2 s pause at top'], {
      frames: [
        "A bell in the hand on the working side, heel below the step's edge",
        'Heel up as high as you can, pause',
      ],
      props: { ...FIGURES['calf-raise'].props, bell: 'near' },
      order: ['armF', 'legF', 'torso', 'head', 'legN', 'armN', 'bell'],
      start: {
        ...FIGURES['calf-raise'].start,
        armN: { dir: -92, reach: 0.995 },
        armF: { at: [30, 140], angle: 10 },
      },
      end: {
        ...FIGURES['calf-raise'].end,
        armN: { dir: -92, reach: 0.995 },
        armF: { at: [30, 140], angle: 10 },
      },
    }),
  },
  'copenhagen-plank': {
    'Ankle on a chair': ANKLE_ON_CHAIR,
    'Ankle on a chair, 3 s lowering': ANKLE_ON_CHAIR,
  },
  'reverse-nordic': {
    'Lean deeper, 3 s lowering': leanBack(
      ['Kneeling upright, feet anchored', 'Leaning further back, slowly, knees to head in line'],
      140,
      [12, 22],
      -98,
    ),
    'To the floor, hands push you back': leanBack(
      ['Kneeling upright, feet anchored', 'Back until your hands reach the floor behind you'],
      156,
      [-34.2, 23.7],
      -118,
    ),
    'To the floor and back, no hands': leanBack(
      ['Kneeling upright, feet anchored', 'Back towards the floor and up again, no hands'],
      156,
      [12, 22],
      -118,
    ),
  },
  'push-up': {
    'Feet elevated': {
      frames: ['Feet on a chair, arms straight, body in one line', 'Chest a fist above the floor'],
      view: [-64, 174, -3, 100],
      props: { ...push.props, ...ON_CHAIR },
      ...plank(push, [-14.6, 45], [0.3, -14.1]),
    },
    Deficit: {
      frames: ['Hands raised on two blocks or books, arms straight', 'Chest down past your hands'],
      view: [-14, 174, -3, 100],
      props: { ...push.props, step: { x0: 102, x1: 124, top: 15 } },
      ...plank(push, [-2.2, 0], [26.8, 5.5], [111, 18]),
    },
    Archer: {
      frames: [
        'Hands set wide, arms straight',
        'Down over one arm as it bends; the other stays straight out to the side',
      ],
      order: ['armF', 'legF', 'legN', 'torso', 'head', 'armN'],
      start: straightOut(push.start),
      end: straightOut(push.end),
      front: ARCHER,
    },
  },
  'diamond-push-up': {
    'Feet elevated': {
      frames: [
        'Feet on a chair, hands together under your chest',
        'Chest to your hands, elbows in',
      ],
      view: [-64, 174, -3, 100],
      props: { ...diamond.props, ...ON_CHAIR },
      ...plank(diamond, [-14.1, 45], [-0.4, -13.3]),
    },
  },
  'pike-push-up': {
    'Feet on chair': {
      frames: [
        'Feet on a chair, hips high over your shoulders',
        'Top of the head towards the floor',
      ],
      view: [-72, 92, -3, 125],
      props: { ...pike.props, chair: { x0: -66, x1: -14, seat: 45 } },
      start: {
        hip: [43.6, 100.5],
        lean: 165,
        ...PIKE_FEET,
        armN: { at: [60, 3], angle: 0 },
        armF: { at: [60, 3], angle: 0 },
      },
      end: {
        hip: [50, 88],
        lean: 170,
        ...PIKE_FEET,
        armN: { at: [60, 3], angle: 0 },
        armF: { at: [60, 3], angle: 0 },
      },
    },
    'Wall handstand push-up negatives': {
      frames: [
        'Upside down, hands on the floor, heels on the wall',
        'Lowered slowly until your head nearly touches the floor',
      ],
      view: [-50, 50, -3, 222],
      props: { mat: [-48, 16], wall: { x0: 17, x1: 25, top: 222 } },
      tempo: [3200, 300, 900, 600],
      start: handstand(57, 180),
      end: handstand(35, 178),
    },
  },
  'back-extension-45': {
    'Holding a plate': { props: { ...FIGURES['back-extension-45'].props, barbell: 'plate' } },
  },
  'kb-curl': {
    '16 kg, hammer grip': {
      frames: ['Handle held upright, elbows at your sides', 'Curled up, handle still upright'],
      props: { bell: 'hammer' },
      start: fist(FIGURES['kb-curl'].start),
      end: fist(FIGURES['kb-curl'].end),
    },
  },
  'glute-bridge': {
    'Standing, at the counter': STANDING_BRIDGE,
    'Shoulders on the sofa (hip thrust)': SOFA_THRUST,
    'Single leg, on the floor': oneLeg(
      {
        view: FIGURES['glute-bridge'].view,
        start: FIGURES['glute-bridge'].start,
        end: FIGURES['glute-bridge'].end,
      },
      ['On your back, one foot down, the other leg up straight', 'Hips up on one leg, hips level'],
      36,
    ),
    'Single leg, shoulders on the sofa': oneLeg(
      SOFA_THRUST,
      ['Upper back on the sofa, one foot down, the other leg up', 'Hips up on one leg, hips level'],
      30,
    ),
  },
  'hip-hinge': {
    'Hands on the counter': COUNTER_HINGE,
    'Hips back to a wall': {
      frames: ['Back to a wall, hands on hips, knees soft', 'Hips pushed back to touch the wall'],
      props: { wall: { x0: -36, x1: -28, top: 200 } },
    },
    'Holding a bag at the chest': {
      frames: ['Standing, a bag hugged to your chest', 'Hips back, back flat, the bag held close'],
      props: { bag: 'chest' },
      order: ['armF', 'legF', 'torso', 'head', 'legN', 'bell', 'armN'],
      start: hugged(FIGURES['hip-hinge'].start),
      end: hugged(FIGURES['hip-hinge'].end),
    },
  },
}

/** Steps set up differently from their exercise's figure that aren't drawn yet: the lower steps
 * ADR-0083 added below today's bottoms (#508). They show no figure rather than the wrong one
 * (a floor push-up for a push-up against the wall); each comes out of here once it is drawn. */
export const UNDRAWN: Readonly<Record<string, readonly string[]>> = {
  'push-up': [
    'Hands on a wall',
    'Hands on a counter',
    'Hands on a table',
    'Hands on a chair seat against a wall',
    'On the knees',
    'Hands on a stair or low step',
  ],
  'bulgarian-split-squat': [
    'Holding a chair, short range',
    'Holding a chair, full range',
    'Back foot on a low step',
  ],
  'pull-up': ['Feet on a chair', 'Scapular pulls'],
  'kb-row': ['A bag, about 4 kg'],
  'kb-curl': ['Water bottles, about 1 kg', 'A bag, 2-4 kg'],
  'calf-raise': ['Both legs, hands on a wall', 'Both legs, on a step'],
  'copenhagen-plank': ['Knee on a chair, bottom foot helping'],
}

/** ``slug``'s figure as it looks at the ladder step ``step``; nothing for a slug without one, or
 * for a step that isn't drawn yet. */
export function figureFor(slug: string, step?: string): Figure | undefined {
  if (step !== undefined && UNDRAWN[slug]?.includes(step)) return undefined
  const figure: Figure | undefined = FIGURES[slug]
  const change = step === undefined ? undefined : STEPS[slug]?.[step]
  return figure && change ? { ...figure, ...change } : figure
}
