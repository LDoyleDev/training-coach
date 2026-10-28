/**
 * Ladder steps that change how an exercise is set up (ADR-0063, addendum): a load on the back,
 * a bell in each hand, dip bars in place of chairs. Keyed by slug, then by the step's name as
 * plan.toml writes it; each entry says what changes over the exercise's figure. Every other step
 * shows the figure as it is.
 */
import type { Pose } from './body'
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
