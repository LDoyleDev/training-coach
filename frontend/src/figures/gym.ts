/**
 * The gym exercises' figures (ADR-0063), by seed slug, grouped by their kit: the barbell and the
 * bench first. Pose keys are as in poses.ts.
 */
import type { Figure } from './poses'

const STAND = { legN: { at: [0, 7] }, legF: { at: [3, 7] } } as const

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
}
