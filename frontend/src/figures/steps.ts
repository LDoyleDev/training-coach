/**
 * Ladder steps that change how an exercise is set up (ADR-0063, addendum): a load on the back,
 * a bell in each hand, dip bars in place of chairs. Keyed by slug, then by the step's name as
 * plan.toml writes it; each entry says what changes over the exercise's figure. Every other step
 * shows the figure as it is.
 */
import type { Pose, Vec } from './body'
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

const VEST = ['Vest or backpack, 5 kg', 'Vest or backpack, 10 kg', 'Vest or backpack, 15 kg']

/** A kettlebell held by the horns at the chest, elbows down in front of the ribs: the same
 * movement, the hands placed on the trunk so they ride with it. */
const goblet = (figure: Figure, frames: Figure['frames']): Change => {
  const arms = {
    armN: { at: [19, 21], from: 'waist', hand: 0.5 },
    armF: { at: [20, 21.5], from: 'waist', hand: 0.5 },
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

/** A Nordic curl: kneeling tall, heels hooked under a low sofa, the body falling forward in one
 * line from the knees, the hamstrings braking it. The knees and feet are the reverse Nordic's. */
const NORDIC_LEGS = {
  legN: { at: [-42.5, 11.6], angle: -100 },
  legF: { at: [-42.5, 11.6], angle: -100 },
} as const
const nordic = (frames: Figure['frames'], hands: Vec, tempo: Figure['tempo']): Change => ({
  frames,
  view: [-72, 118, -3, 131],
  props: { mat: [-70, 116], bench: { x0: -118, x1: -38, top: 24, behind: true } },
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

export const STEPS: Readonly<Record<string, Readonly<Record<string, Change>>>> = {
  'pull-up': LOADED(VEST, FIGURES['pull-up']),
  'chin-up': LOADED(VEST, FIGURES['chin-up']),
  dip: {
    'Feet off floor': OFF_FLOOR,
    ...each(['Feet off floor, 5 kg vest or backpack', 'Feet off floor, 10 kg'], OFF_FLOOR_LOADED),
    'Dip bars, bodyweight, full range': {
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
    },
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
}

/** ``slug``'s figure as it looks at the ladder step ``step``; nothing for a slug without one. */
export function figureFor(slug: string, step?: string): Figure | undefined {
  const figure: Figure | undefined = FIGURES[slug]
  const change = step === undefined ? undefined : STEPS[slug]?.[step]
  return figure && change ? { ...figure, ...change } : figure
}
