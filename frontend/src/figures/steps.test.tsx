import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import plan from '../../../backend/src/training_coach/seed/plan.toml?raw'
import { BODY, blend, dist, heading, solve, type Vec } from './body'
import { solveFront, type FrontJoints, type FrontLimbJoints, type FrontPose } from './front'
import { layDown, perspectiveShapes } from './perspective'
import Figure from './Figure'
import { FIGURES } from './poses'
import { SOFA, shapes, type Props, type Shape } from './shapes'
import { STEPS, figureFor } from './steps'

const ALONG = [0, 0.25, 0.5, 0.75, 1]

/** The ladder of ``slug`` in plan.toml. */
function ladder(slug: string): string[] {
  // Each exercise's block runs to the next table that isn't its own, such as [exercises.needs].
  const blocks = plan.split('[[exercises]]').map((b) => b.split(/\n\[(?!exercises\.)/)[0])
  const block = blocks.find((b) => b.includes(`slug = "${slug}"\n`) && b.includes('ladder = '))
  const line = (block ?? '').split('\n').find((l) => l.startsWith('ladder = ')) ?? 'ladder = []'
  return JSON.parse(line.slice('ladder = '.length)) as string[]
}

/** The audit (ADR-0063, addendum of 27 Oct): the steps of an exercise with a figure that show
 * the figure as it is, and why. The figure draws one of them; the rest change only the tempo, a
 * pause, the weight of a bell already drawn, or how far a movement drawn the same way goes. Every
 * other step is drawn in steps.ts. A ladder of one step is its figure. */
const SAME: Readonly<Record<string, Readonly<Record<string, string>>>> = {
  'tibialis-raise': { 'Back against wall, heels forward': 'the figure' },
  'jump-squat': {
    'Bodyweight, full rest': 'the figure',
    'Pause at bottom, then jump': 'a pause',
  },
  'kb-swing': {
    'Two-hand, 8 kg': 'the figure',
    'Two-hand, 16 kg': 'a heavier bell',
    'Two-hand, 24 kg': 'a heavier bell',
  },
  'bulgarian-split-squat': { 'Bodyweight, back foot on chair': 'the figure' },
  'pistol-squat': { 'Full pistol': 'the figure' },
  'single-leg-rdl': {
    '8 kg': 'the figure, a bell in the hand',
    '8 kg, pause at bottom': 'a pause',
    '16 kg': 'a heavier bell',
    '16 kg, pause at bottom': 'a heavier bell and a pause',
  },
  'hamstring-curl': { 'Towel slide, both legs': 'the figure' },
  'calf-raise': { 'Bodyweight on a step': 'the figure' },
  'pull-up': {
    'Slow negatives': 'the same path, lowering slowly',
    'Strict pull-up': 'the figure',
    'Pause at top': 'a pause',
  },
  dip: { 'Feet on floor': 'the figure' },
  'kb-row': {
    '8 kg': 'the figure, a bell in the hand',
    '8 kg, 3 s lowering': 'the tempo',
    '16 kg': 'a heavier bell',
    '16 kg, 3 s lowering': 'a heavier bell and the tempo',
    '16 kg, pause at top': 'a heavier bell and a pause',
  },
  'push-up': { Standard: 'the figure' },
  'pike-push-up': { 'Feet on floor': 'the figure' },
  'chin-up': { Strict: 'the figure', '3 s lowering': 'the tempo' },
  'diamond-push-up': { Standard: 'the figure' },
  'kb-curl': {
    '8 kg': 'the figure, a bell in the hand',
    '8 kg, slow tempo': 'the tempo',
    '8 kg, 3 s lowering, pause at top': 'the tempo and a pause',
    '16 kg, slow tempo': 'a heavier bell and the tempo',
  },
  'copenhagen-plank': {
    'Knee on a chair': 'the figure',
    'Knee on a chair, 3 s lowering': 'the tempo',
  },
  'reverse-nordic': { 'Lean back about 30 degrees': 'the figure' },
  // The gym figures (#397): the plate is drawn there.
  'back-extension-45': { Bodyweight: 'the figure' },
  // The entry exercises (ADR-0083) that share a flow movement's figure.
  'glute-bridge': {
    'On the floor': 'the figure',
    'On the floor, 3 s hold at the top': 'a pause',
  },
  // The entry exercises for the upper body and bands, and the adductor and hamstring moves
  // (entry-upper.ts).
  'armchair-press-up': {
    'Feet helping': 'the figure',
    'Arms only, feet resting': 'the same picture: the feet stay down, only taking no weight',
    'Arms only, 2 s hold at the top': 'the same picture and a pause',
  },
  'band-pushdown': {
    'Light band': 'the figure, a band in the hands',
    'Medium band': 'a stronger band',
    'Heavy band': 'a stronger band, a step further from the door',
  },
  'band-row': {
    'Light band': 'the figure, a band in the hands',
    'Medium band': 'a stronger band',
    'Heavy band': 'a stronger band, the chair further back',
  },
  'band-pull-apart': {
    'Light band': 'the figure, a band between the hands',
    'Medium band': 'a stronger band',
    'Heavy band': 'a stronger band',
  },
  'band-pulldown': {
    'Light band': 'the figure, a band in the hands',
    'Medium band': 'a stronger band',
    'Heavy band': 'a stronger band, the chair further back',
  },
  'seated-press': {
    'Small water bottles': 'the figure, a bottle in each hand',
    'Large water bottles': 'bigger bottles',
  },
  'adductor-squeeze': { 'Seated pillow squeeze, 5 s hold': 'the figure' },
  'standing-leg-curl': { 'At the counter': 'the figure' },
}

test('every step of an exercise with a figure is drawn, or listed as showing it as it is', () => {
  const unmet: string[] = []
  for (const slug of Object.keys(FIGURES)) {
    const steps = ladder(slug)
    if (steps.length < 2) continue
    for (const step of steps) {
      const drawn = step in (STEPS[slug] ?? {})
      const same = step in (SAME[slug] ?? {})
      if (drawn === same) unmet.push(`${slug} / ${step}`)
    }
  }
  expect(unmet, 'draw these in steps.ts, or say in SAME why the figure fits').toEqual([])
  for (const [slug, why] of Object.entries(SAME))
    for (const step of Object.keys(why)) expect(ladder(slug), slug).toContain(step)
})

/** Every exercise's figure at every step that changes it. */
const VARIANTS = Object.entries(STEPS).flatMap(([slug, steps]) =>
  Object.keys(steps).map((step) => ({ slug, step, figure: figureFor(slug, step)! })),
)

test("every step that changes a figure is a step on that exercise's ladder", () => {
  expect(VARIANTS.length).toBeGreaterThan(8)
  for (const { slug, step } of VARIANTS) expect(ladder(slug), slug).toContain(step)
})

test('another step, or none, shows the figure as it is; no figure, nothing', () => {
  expect(figureFor('dip')).toBe(FIGURES.dip)
  expect(figureFor('dip', 'Feet on floor')).toBe(FIGURES.dip)
  expect(figureFor('no-such-move', 'Dip bars, bodyweight, full range')).toBeUndefined()
  const loaded = figureFor('pull-up', 'Vest or backpack')!
  expect(loaded.props).toEqual({ ...FIGURES['pull-up'].props, load: true })
  expect(loaded.start).toBe(FIGURES['pull-up'].start)
})

test("every step's figure keeps its limbs, stays in its picture and off the floor", () => {
  for (const { slug, step, figure } of VARIANTS) {
    const name = `${slug} / ${step}`
    const [x0, x1, , y1] = figure.view
    for (const t of ALONG) {
      const pose = blend(figure.start, figure.end, t)
      const j = solve(pose)
      for (const leg of [j.legN, j.legF]) {
        expect(dist(leg.hip, leg.knee), name).toBeCloseTo(BODY.thigh, 1)
        expect(dist(leg.knee, leg.ankle), name).toBeCloseTo(BODY.shin, 1)
      }
      for (const arm of [j.armN, j.armF]) {
        expect(dist(arm.shoulder, arm.elbow), name).toBeLessThan(BODY.upperArm + 0.05)
        expect(dist(arm.elbow, arm.wrist), name).toBeLessThan(BODY.forearm + 0.05)
      }
      const points = [j.hip, j.shoulder, j.head.c, j.armN.tip, j.armF.tip]
      for (const l of [j.legN, j.legF]) points.push(l.knee, l.heel, l.ball, l.tip)
      for (const p of points) {
        expect(p[0], name).toBeGreaterThan(x0)
        expect(p[0], name).toBeLessThan(x1)
        expect(p[1], name).toBeGreaterThan(-0.5)
        expect(p[1], name).toBeLessThan(y1)
      }
      expect(j.head.c[1] + 11.5, name).toBeLessThan(y1)
      for (const shape of shapes(pose, figure.props, figure.order))
        expect(JSON.stringify(shape), name).not.toMatch(/NaN|null/)
    }
  }
})

const bells = (drawn: Shape[]) => drawn.filter((s) => s.kind === 'ball' && s.tone === 'bell')

test('a vest or backpack sits on the upper back, behind the body', () => {
  const pull = figureFor('pull-up', 'Vest or backpack')!
  const drawn = shapes(pull.start, pull.props, pull.order)
  const plain = shapes(FIGURES['pull-up'].start, FIGURES['pull-up'].props)
  expect(drawn).toHaveLength(plain.length + 2) // the pack and a strap
  const pack = drawn.findIndex((s, i) => i > 2 && s.kind === 'path' && s.tone === 'bell')
  const hip = drawn.findIndex((s) => s.kind === 'ball' && s.tone === 'near' && s.r === 7.6)
  expect(pack).toBeLessThan(hip) // drawn before the trunk: behind it
  const shape = drawn[pack]
  const xs = [...(shape.kind === 'path' ? shape.d.matchAll(/(-?[\d.]+) (-?[\d.]+)/g) : [])].map(
    (m) => Number(m[1]),
  )
  expect(Math.max(...xs), 'behind the back').toBeLessThan(solve(pull.start).shoulder[0])
})

test('on dip bars the hands stay on the bar and the feet stay off the floor', () => {
  const bars = figureFor('dip', 'Dip bars, bodyweight, full range')!
  const { top } = bars.props!.bars!
  expect(bars.props!.chair).toBeUndefined() // bars in place of the chairs
  for (const t of ALONG) {
    const j = solve(blend(bars.start, bars.end, t))
    for (const arm of [j.armN, j.armF]) expect(arm.wrist[1] - top).toBeCloseTo(3.5, 0)
    for (const leg of [j.legN, j.legF])
      expect(Math.min(leg.heel[1], leg.ball[1], leg.tip[1]), 'feet off').toBeGreaterThan(20)
  }
  const [up, down] = [solve(bars.start), solve(bars.end)]
  expect(dist(up.shoulder, up.armN.wrist), 'arms straight').toBeGreaterThan(54)
  expect(down.armN.elbow[0], 'elbows back').toBeLessThan(down.shoulder[0] - 15)
  expect(Math.abs(down.armN.elbow[1] - down.shoulder[1]), 'upper arm about level').toBeLessThan(8)
})

test('on dip bars with a vest or backpack, the same dip carries the pack', () => {
  const bars = figureFor('dip', 'Dip bars, bodyweight, full range')!
  const loaded = figureFor('dip', 'Dip bars, vest or backpack')!
  expect(loaded.props).toEqual({ ...bars.props, load: true })
  expect([loaded.start, loaded.end]).toEqual([bars.start, bars.end])
  expect(shapes(loaded.start, loaded.props)).toHaveLength(shapes(bars.start, bars.props).length + 2)
})

test('feet off the floor, the dip hangs between two chairs, knees bent, feet behind', () => {
  const steps = ['Feet off floor', 'Feet off floor, 5 kg vest or backpack', 'Feet off floor, 10 kg']
  for (const step of steps) {
    const dip = figureFor('dip', step)!
    const { seat, beside } = dip.props!.chair!
    expect(beside, step).toBe(true)
    expect(dip.props!.load ?? false, step).toBe(step !== 'Feet off floor')
    for (const t of ALONG) {
      const j = solve(blend(dip.start, dip.end, t))
      for (const arm of [j.armN, j.armF]) expect(arm.wrist[1] - seat).toBeCloseTo(3.4, 0)
      for (const leg of [j.legN, j.legF]) {
        expect(leg.knee[1] - 5.4, `${step}: knees well off the floor`).toBeGreaterThan(10)
        expect(Math.min(leg.heel[1], leg.ball[1], leg.tip[1]), 'feet up').toBeGreaterThan(40)
        expect(leg.ankle[1], 'feet above the knees').toBeGreaterThan(leg.knee[1] + 20)
        expect(leg.ankle[0], 'feet behind').toBeLessThan(leg.knee[0] - 15)
        const knee = Math.abs(heading(leg.knee, leg.hip) - heading(leg.knee, leg.ankle))
        expect(knee, 'knee bent about square').toBeGreaterThan(70)
        expect(knee).toBeLessThan(100)
      }
    }
    const [up, down] = [solve(dip.start), solve(dip.end)]
    expect(dist(up.shoulder, up.armN.wrist), 'arms straight').toBeGreaterThan(54)
    expect(down.armN.elbow[0], 'elbows back').toBeLessThan(down.shoulder[0] - 15)
    expect(up.shoulder[1] - down.shoulder[1], 'down').toBeGreaterThan(20)
    // The near chair hides the far one, so it is drawn last, in front of the body.
    const drawn = shapes(dip.start, dip.props, dip.order)
    const tone = (shape?: Shape) => (shape && 'tone' in shape ? shape.tone : undefined)
    expect(tone(drawn.at(-1))).toBe('prop')
    expect(tone(drawn[0])).not.toBe('prop')
  }
  expect(figureFor('dip', 'Feet on floor')!.props!.chair!.beside).toBeUndefined()
})

test("a suitcase hold hangs a bell from each hand, the heavier on the front leg's side", () => {
  const split = figureFor('bulgarian-split-squat', 'Suitcase hold, 16 kg + 8 kg')!
  for (const pose of [split.start, split.end]) {
    const j = solve(pose)
    const [far, near] = bells(shapes(pose, split.props, split.order))
    if (far.kind !== 'ball' || near.kind !== 'ball') throw new Error('two bells')
    expect(near.r).toBeGreaterThan(far.r)
    expect(near.c[0]).toBeCloseTo(j.armN.wrist[0], 5)
    expect(far.c[0]).toBeCloseTo(j.armF.wrist[0], 5)
    for (const b of [near, far]) expect(-b.c[1] - b.r, 'clear of the floor').toBeGreaterThan(3)
  }
  expect(FIGURES['bulgarian-split-squat'].props!.bell).toBeUndefined() // other steps: no bells
})

test('a curl keeps the elbows pinned; the hammer grip holds the handle upright', () => {
  for (const t of ALONG) {
    const j = solve(blend(FIGURES['kb-curl'].start, FIGURES['kb-curl'].end, t))
    expect(Math.abs(j.armN.elbow[0] - j.shoulder[0])).toBeLessThan(2)
    expect(j.shoulder[1] - j.armN.elbow[1]).toBeCloseTo(BODY.upperArm, 1)
  }
  const top = solve(FIGURES['kb-curl'].end)
  expect(top.armN.wrist[1], 'curled up').toBeGreaterThan(top.armN.elbow[1] + 20)
  const ring = (step: string) => {
    const f = figureFor('kb-curl', step)!
    const found = shapes(f.start, f.props, f.order).find((s) => s.kind === 'ring')
    if (found?.kind !== 'ring') throw new Error('no handle')
    return found
  }
  const hammer = ring('16 kg, hammer grip')
  expect(hammer.ry).toBeGreaterThan(hammer.r * 1.5) // stood upright
  expect(ring('8 kg').ry).toBeUndefined()
})

test('the figure shows the set-up of the step it is given', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  render(<Figure slug="dip" name="Dip" step="Dip bars, bodyweight, full range" />)
  expect(screen.getByRole('img', { name: /^Dip, start: Arms straight on the bars/ })).toBeVisible()
  vi.unstubAllGlobals()
})

const GOBLET = [
  ...[
    'Goblet hold, 8 kg',
    'Goblet hold, 3 s lowering',
    'Goblet hold, 16 kg',
    'Goblet hold 16 kg, 3 s lowering',
  ].map((step) => ['bulgarian-split-squat', step] as const),
  ['jump-squat', 'Holding 8 kg'] as const,
  ['pistol-squat', 'Holding 8 kg'] as const,
]

test('a goblet hold holds the bell at the chest, in front of the body, all the way', () => {
  for (const [slug, step] of GOBLET) {
    const held = figureFor(slug, step)!
    expect(held.props!.bell, step).toBe('goblet')
    expect(held.props!.chair, 'the chair stays').toEqual(FIGURES[slug].props?.chair)
    for (const t of ALONG) {
      const pose = blend(held.start, held.end, t)
      const j = solve(pose)
      const drawn = shapes(pose, held.props, held.order)
      const [bell] = bells(drawn)
      if (bell?.kind !== 'ball') throw new Error('a bell')
      const c: Vec = [bell.c[0], -bell.c[1]]
      expect(c[0], `${slug}: in front of the chest`).toBeGreaterThan(j.midChest[0])
      expect(dist(j.armN.wrist, j.armF.wrist), 'both hands on it').toBeLessThan(3)
      expect(dist(c, j.armN.wrist), 'under the hands').toBeLessThan(11)
      expect(c[1], 'under the hands').toBeLessThan(j.armN.wrist[1])
      expect(dist(j.armN.wrist, j.midChest), 'in front of the chest').toBeLessThan(40)
      const torso = drawn.findIndex((s) => s.kind === 'ball' && s.tone === 'near' && s.r === 7.6)
      expect(drawn.indexOf(bell), 'in front of the body').toBeGreaterThan(torso)
    }
  }
})

test('a single-leg curl slides one heel and holds the other leg up, straight', () => {
  const curl = figureFor('hamstring-curl', 'Towel slide, single leg')!
  for (const t of ALONG) {
    const j = solve(blend(curl.start, curl.end, t))
    expect(j.legN.heel[1], 'heel on the towel').toBeLessThan(6)
    expect(dist(j.legF.hip, j.legF.ankle), 'straight').toBeGreaterThan(BODY.thigh + BODY.shin - 1)
    expect(Math.min(j.legF.heel[1], j.legF.ankle[1]), 'off the floor').toBeGreaterThan(55)
  }
  const [long, curled] = [solve(curl.start), solve(curl.end)]
  expect(curled.legN.heel[0], 'heel pulled in').toBeLessThan(long.legN.heel[0] - 30)
})

test('a Nordic curl falls forward in one line from knees that stay put', () => {
  for (const step of ['Nordic curl negatives', 'Full Nordic curl']) {
    const nordic = figureFor('hamstring-curl', step)!
    expect(nordic.props!.towel, 'no towel').toBeUndefined()
    for (const t of ALONG) {
      const j = solve(blend(nordic.start, nordic.end, t))
      expect(dist(j.legN.knee, [0.1, 5.4]), `${step}: knee put`).toBeLessThan(0.5)
      const thigh = heading(j.legN.knee, j.hip)
      expect(Math.abs(heading(j.hip, j.neckBase) - thigh), 'one line').toBeLessThan(1)
      expect(j.legN.ankle[1], 'feet anchored').toBeCloseTo(11.6, 1)
    }
    const [tall, low] = [solve(nordic.start), solve(nordic.end)]
    expect(tall.neckBase[1], 'tall').toBeGreaterThan(90)
    expect(low.neckBase[1], 'lowered').toBeLessThan(40)
    expect(low.armN.wrist[1] < 4, `${step}: hands on the floor`).toBe(
      step === 'Nordic curl negatives',
    )
    // A sofa, not a low bench: seat, arm and back, the heels hooked under its front.
    const { sofa } = nordic.props!
    expect(nordic.props!.bench, 'no bench').toBeUndefined()
    expect(tall.legN.heel[0], 'heels under the sofa').toBeGreaterThan(sofa!.x0)
    expect(tall.legN.heel[0], 'heels under the sofa').toBeLessThan(sofa!.x1)
    expect(tall.legN.ankle[1] + 4, 'under its frame').toBeLessThan(SOFA.under)
    expect(SOFA.back).toBeGreaterThan(SOFA.arm)
    expect(SOFA.arm).toBeGreaterThan(SOFA.seat)
    const paths = (props?: Props) =>
      shapes(nordic.start, props).filter((d) => d.kind === 'path').length
    expect(paths(nordic.props) - paths(), 'legs, frame, cushion, arm, back').toBe(7)
  }
})

test('kneeling figures fill their picture: no empty band above the head', () => {
  const steps = ['Lean deeper, 3 s lowering', 'To the floor, hands push you back', undefined]
  const kneeling = [
    ...steps.map((step) => figureFor('reverse-nordic', step)!),
    figureFor('hamstring-curl', 'Nordic curl negatives')!,
  ]
  for (const figure of kneeling) {
    const top = solve(figure.start).head.c[1] + 11.5
    expect(figure.view[3] - top, figure.frames[1]).toBeLessThan(6)
  }
})

/** How big ``figure`` is drawn at 360px, in px per cm: its two stills one above the other at
 * full width when wide, else side by side, none taller than 288px (Figure.tsx). */
const perCm = ({ view: [x0, x1, y0, y1] }: { view: readonly number[] }) => {
  const width = (x1 - x0) / (y1 - y0) > 1.3 ? 328 : (328 - 12) / 2
  return Math.min(width / (x1 - x0), 288 / (y1 - y0))
}

test('a Nordic curl is drawn as big as a reverse Nordic, its sofa in the picture', () => {
  for (const step of ['Nordic curl negatives', 'Full Nordic curl']) {
    const nordic = figureFor('hamstring-curl', step)!
    expect(perCm(nordic), step).toBeGreaterThanOrEqual(perCm(FIGURES['reverse-nordic']))
    const [x0, x1] = nordic.view
    for (const t of ALONG)
      for (const shape of shapes(blend(nordic.start, nordic.end, t), nordic.props)) {
        const xs =
          shape.kind === 'path'
            ? [...shape.d.matchAll(/(-?[\d.]+) (-?[\d.]+)/g)].map((m) => +m[1])
            : shape.kind === 'ball'
              ? [shape.c[0] - shape.r, shape.c[0] + shape.r]
              : []
        for (const x of xs) {
          expect(x, step).toBeGreaterThan(x0)
          expect(x, step).toBeLessThan(x1)
        }
      }
  }
})

test('a pistol to a seat sits down onto it, on one leg, the other leg out straight', () => {
  const seats = { 'Sit to chair on one leg': 45, 'Lower box': 32 }
  for (const [step, top] of Object.entries(seats)) {
    const sit = figureFor('pistol-squat', step)!
    const { chair, step: box } = sit.props!
    const [x0, x1] = chair ? [chair.x0, chair.x1] : [box!.x0, box!.x1]
    expect(chair?.seat ?? box?.top, step).toBe(top)
    expect(sit.start, 'starts as the pistol does').toBe(FIGURES['pistol-squat'].start)
    for (const t of ALONG) {
      const j = solve(blend(sit.start, sit.end, t))
      expect(dist(j.legN.ankle, [0, 7]), 'the standing foot stays').toBeLessThan(0.01)
      expect(dist(j.legF.hip, j.legF.ankle), 'the free leg straight').toBeGreaterThan(80)
      expect(Math.min(j.legF.heel[1], j.legF.tip[1]), 'and off the floor').toBeGreaterThan(5)
    }
    const down = solve(sit.end)
    expect(down.hip[1] - top, `${step}: sat on it`).toBeGreaterThan(6)
    expect(down.hip[1] - top).toBeLessThan(12)
    expect(down.hip[0] - 8, 'the seat under you').toBeGreaterThan(Math.min(x0, x1))
    expect(down.hip[0] - 8).toBeLessThan(Math.max(x0, x1))
  }
})

test('the calf raise holds its bell on the working side, clear of the step', () => {
  for (const step of ['Holding 8 kg', '8 kg, 2 s pause at top']) {
    const calf = figureFor('calf-raise', step)!
    const { step: block, wall } = calf.props!
    for (const t of ALONG) {
      const pose = blend(calf.start, calf.end, t)
      const j = solve(pose)
      const [bell] = bells(shapes(pose, calf.props, calf.order))
      if (bell?.kind !== 'ball') throw new Error('a bell')
      expect(bell.c[0], step).toBeCloseTo(j.armN.wrist[0], 5)
      expect(-bell.c[1] - bell.r, 'clear of the step').toBeGreaterThan(block!.top + 20)
      expect(j.armF.wrist[0], 'the other hand on the wall').toBeCloseTo(wall!.x0 - 10, 0)
    }
  }
})

test('tibialis raises: heels further out, on one foot, or lifting a bell on the toes', () => {
  const base = solve(FIGURES['tibialis-raise'].start)
  const out = solve(figureFor('tibialis-raise', 'Heels further from wall')!.start)
  expect(out.legN.heel[0] - base.legN.heel[0], 'further out').toBeGreaterThan(10)
  expect(out.shoulder[0] - 13.5, 'back still on the wall').toBeLessThan(-43)
  const one = figureFor('tibialis-raise', 'Single leg')!
  for (const t of ALONG) {
    const j = solve(blend(one.start, one.end, t))
    expect(j.legN.heel[1], 'on one heel').toBeLessThan(2)
    expect(Math.min(j.legF.heel[1], j.legF.tip[1]), 'the other foot up').toBeGreaterThan(15)
  }
  const toes = figureFor('tibialis-raise', 'Holding 8 kg on toes')!
  const [low, high] = [toes.start, toes.end].map((pose) => {
    const [bell] = bells(shapes(pose, toes.props, toes.order))
    if (bell?.kind !== 'ball') throw new Error('a bell')
    expect(-bell.c[1] - bell.r, 'resting on the foot, off the floor').toBeGreaterThan(1)
    const foot = solve(pose).legN
    expect(bell.c[0], 'over the forefoot').toBeGreaterThan(foot.ankle[0])
    expect(bell.c[0]).toBeLessThan(foot.tip[0])
    return -bell.c[1]
  })
  expect(high - low, 'lifted with the toes').toBeGreaterThan(5)
})

test('a one-arm swing holds the bell in one hand, the other hand at your side', () => {
  for (const step of ['One-arm, 8 kg', 'One-arm, 16 kg']) {
    const swing = figureFor('kb-swing', step)!
    for (const t of ALONG) {
      const pose = blend(swing.start, swing.end, t)
      const j = solve(pose)
      const drawn = shapes(pose, swing.props, swing.order)
      const ring = drawn.find((s) => s.kind === 'ring')
      if (ring?.kind !== 'ring') throw new Error('a handle')
      expect(dist([ring.c[0], -ring.c[1]], j.armN.wrist), step).toBeLessThan(4)
    }
    for (const pose of [swing.start, swing.end]) {
      const j = solve(pose)
      expect(dist(j.armF.wrist, j.armN.wrist), 'the free hand off it').toBeGreaterThan(15)
    }
    expect(solve(swing.end).armF.wrist[1], 'at your side').toBeLessThan(solve(swing.end).hip[1])
  }
})

test('a Copenhagen plank with the ankle on the chair keeps the top leg straight on the seat', () => {
  for (const step of ['Ankle on a chair', 'Ankle on a chair, 3 s lowering']) {
    const plank = figureFor('copenhagen-plank', step)!
    const { bench } = plank.props!
    const seat = plank.front!.seat!
    const onSeat = (ankle: Vec, { x0, x1, top }: { x0: number; x1: number; top: number }) => {
      expect(ankle[1] - top, `${step}: the ankle on the seat`).toBeGreaterThan(3)
      expect(ankle[1] - top).toBeLessThan(7)
      expect(ankle[0]).toBeGreaterThan(x0)
      expect(ankle[0]).toBeLessThan(x1)
    }
    for (const t of ALONG) {
      const side = solve(blend(plank.start, plank.end, t))
      onSeat(side.legN.ankle, bench!)
      expect(dist(side.hip, side.legN.ankle), 'top leg straight').toBeGreaterThan(
        BODY.thigh + BODY.shin - 1,
      )
      expect(dist(side.armF.elbow, [0, 4]), 'elbow under the shoulder').toBeLessThan(3)
      const front = solveFront(blend(plank.front!.start, plank.front!.end, t))
      onSeat(front.legR.end, seat)
      expect(dist(front.legR.root, front.legR.end), 'straight').toBeGreaterThan(
        BODY.thigh + BODY.shin - 2,
      )
      expect(dist(front.armL.mid, [0, 4]), 'elbow under the shoulder').toBeLessThan(3)
    }
    const [low, high] = [solve(plank.start), solve(plank.end)]
    expect(high.hip[1] - low.hip[1], 'hips up').toBeGreaterThan(15)
    const line = heading(high.legN.ankle, high.shoulder)
    expect(Math.abs(heading(high.legN.ankle, high.hip) - line), 'one line').toBeLessThan(2)
  }
})

test('a reverse Nordic leans further back the further up the ladder, knees put, body in line', () => {
  const lean = (step?: string) => {
    const figure = figureFor('reverse-nordic', step)!
    for (const t of ALONG) {
      const j = solve(blend(figure.start, figure.end, t))
      if (step) expect(dist(j.legN.knee, [0.1, 5.4]), `${step}: knees put`).toBeLessThan(0.5)
      expect(
        Math.abs(heading(j.legN.knee, j.hip) - heading(j.hip, j.neckBase)),
        'in line',
      ).toBeLessThan(1)
      expect(j.head.c[1] - 11.5, 'head off the floor').toBeGreaterThan(20)
    }
    const end = solve(figure.end)
    return { back: heading(end.legN.knee, end.hip), hands: end.armN.tip[1] }
  }
  const base = lean()
  const deeper = lean('Lean deeper, 3 s lowering')
  const hands = lean('To the floor, hands push you back')
  const none = lean('To the floor and back, no hands')
  expect(deeper.back).toBeGreaterThan(base.back + 15)
  expect(hands.back).toBeGreaterThan(deeper.back + 10)
  expect(none.back).toBe(hands.back)
  expect(hands.hands, 'hands to the floor').toBeLessThan(3)
  expect(none.hands, 'arms crossed').toBeGreaterThan(40)
})

test('push-ups with the feet on a chair: toes on the seat, the body sloping down to the hands', () => {
  for (const slug of ['push-up', 'diamond-push-up']) {
    const up = figureFor(slug, 'Feet elevated')!
    const { seat, x0, x1 } = up.props!.chair!
    for (const t of ALONG) {
      const j = solve(blend(up.start, up.end, t))
      for (const leg of [j.legN, j.legF]) {
        expect(leg.ball[1], `${slug}: on the seat`).toBeCloseTo(seat, 5)
        expect(leg.tip[1], 'toes not through it').toBeGreaterThan(seat - 0.5)
        expect(leg.ball[0]).toBeGreaterThan(Math.min(x0, x1))
        expect(leg.ball[0]).toBeLessThan(Math.max(x0, x1))
      }
      expect(j.armN.wrist[1], 'hands on the floor').toBeCloseTo(3, 5)
    }
    const low = solve(up.end)
    expect(low.shoulder[1], 'shoulders below the feet').toBeLessThan(low.legN.ankle[1] - 20)
  }
})

test('a deficit push-up has the hands on blocks and the chest going down past them', () => {
  const deficit = figureFor('push-up', 'Deficit')!
  const { top, x0, x1 } = deficit.props!.step!
  for (const pose of [deficit.start, deficit.end]) {
    const j = solve(pose)
    expect(j.armN.wrist[1] - top, 'hands on the block').toBeCloseTo(3, 5)
    expect(j.armN.wrist[0]).toBeGreaterThan(x0)
    expect(j.armN.wrist[0]).toBeLessThan(x1)
  }
  expect(solve(deficit.end).shoulder[1] - 12, 'chest below the hands').toBeLessThan(top)
})

test('an archer push-up keeps one arm straight while the other bends', () => {
  const archer = figureFor('push-up', 'Archer')!
  for (const t of ALONG) {
    const j = solve(blend(archer.start, archer.end, t))
    const { shoulder, elbow, wrist } = j.armN
    const off = Math.abs(heading(shoulder, elbow) - heading(elbow, wrist))
    expect(off, 'the near arm straight').toBeLessThan(4)
  }
  const low = solve(archer.end).armF
  const bend = Math.abs(heading(low.elbow, low.shoulder) - heading(low.elbow, low.wrist))
  expect(Math.min(bend, 360 - bend), 'the far arm bent').toBeLessThan(120)
  expect(archer.order!.at(-1), 'the straight arm in front').toBe('armN')
})

test('pike push-ups go further upside down: feet on a chair, then a handstand at a wall', () => {
  const chair = figureFor('pike-push-up', 'Feet on chair')!
  const { seat } = chair.props!.chair!
  for (const t of ALONG) {
    const j = solve(blend(chair.start, chair.end, t))
    for (const leg of [j.legN, j.legF])
      expect(Math.min(leg.ball[1], leg.tip[1]), 'toes on the seat').toBeCloseTo(seat, 0)
    expect(j.hip[1], 'hips over the shoulders').toBeGreaterThan(j.shoulder[1] + 25)
    expect(j.armN.wrist[1]).toBeCloseTo(3, 5)
  }
  const wall = figureFor('pike-push-up', 'Wall handstand push-up negatives')!
  const { x0 } = wall.props!.wall!
  for (const t of ALONG) {
    const j = solve(blend(wall.start, wall.end, t))
    expect(j.head.c[1], 'upside down').toBeLessThan(j.hip[1] - 50)
    expect(j.legN.ankle[1], 'feet up').toBeGreaterThan(j.hip[1] + 80)
    expect(x0 - j.legN.heel[0], 'heels on the wall').toBeLessThan(3)
    expect(x0 - j.legN.heel[0]).toBeGreaterThan(0)
    expect(j.armN.wrist[1]).toBeCloseTo(3, 5)
    expect(j.head.c[1] - 11.5, 'head off the floor').toBeGreaterThan(0)
  }
  expect(solve(wall.start).head.c[1] - solve(wall.end).head.c[1], 'lowered').toBeGreaterThan(15)
})

test('an archer push-up is seen from in front of the head: one arm bends, the other stays straight', () => {
  const front = figureFor('push-up', 'Archer')!.front!
  type Seen = { pose: FrontPose; j: FrontJoints }
  const [top, low]: Seen[] = [front.start, front.end].map((pose) => ({ pose, j: solveFront(pose) }))
  const world = (pose: FrontPose, p: Vec, z: number) => layDown([p[0], p[1], z], pose.lie!)
  const reach = (arm: FrontLimbJoints) =>
    Math.hypot(arm.end[0] - arm.root[0], arm.end[1] - arm.root[1], arm.z[1])
  const hands = ({ pose, j }: Seen) => [j.armL, j.armR].map((arm) => world(pose, arm.end, arm.z[1]))
  for (const [a, b] of [0, 1].map((i) => [hands(top)[i], hands(low)[i]])) {
    expect(Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]), 'hands put').toBeLessThan(0.5)
    expect(a[1], 'on the floor').toBeLessThan(4)
  }
  for (const { pose, j } of [top, low])
    for (const leg of [j.legL, j.legR])
      expect(world(pose, [leg.end[0], leg.end[1] - 1], 13)[1], 'toes down').toBeLessThan(2)
  expect(reach(top.j.armL), 'straight').toBeGreaterThan(55.5)
  expect(reach(top.j.armR), 'straight').toBeGreaterThan(55.5)
  expect(reach(low.j.armL), 'still straight, out to the side').toBeGreaterThan(55.5)
  expect(reach(low.j.armR), 'bent').toBeLessThan(35)
  const shoulders = (t: Seen) => world(t.pose, t.j.shoulders, 0)[1]
  expect(shoulders(low), 'down').toBeLessThan(shoulders(top) - 15)
  expect(low.j.hip[0], 'over the bent arm').toBeLessThan(top.j.hip[0] - 10)
  const drawn = perspectiveShapes(front.end, front.camera, undefined, front)
  expect(JSON.stringify(drawn)).not.toMatch(/NaN|null/)
})

test('the bridge at the counter keeps both hands on it and the standing foot down', () => {
  const figure = figureFor('glute-bridge', 'Standing, at the counter')!
  for (const t of ALONG) {
    const j = solve(blend(figure.start, figure.end, t))
    expect(Math.abs(j.armN.wrist[1] - 92)).toBeLessThan(1) // on the counter's top
    expect(j.legF.ankle).toEqual(solve(figure.start).legF.ankle)
  }
  const back = solve(figure.end).legN
  expect(back.ankle[0], 'the working leg goes back').toBeLessThan(-25)
  expect(dist(back.hip, back.ankle), 'straight').toBeGreaterThan(BODY.thigh + BODY.shin - 1)
})

test('a bag hugged in the hinge is held at the hands, and a hip thrust lifts off the sofa', () => {
  const figure = figureFor('hip-hinge', 'Holding a bag at the chest')!
  for (const t of [0, 1]) {
    const pose = blend(figure.start, figure.end, t)
    const bag = shapes(pose, figure.props, figure.order).filter(
      (s) => s.kind === 'path' && s.tone === 'bell',
    )
    expect(bag).toHaveLength(1)
  }
  const thrust = figureFor('glute-bridge', 'Shoulders on the sofa (hip thrust)')!
  expect(solve(thrust.end).hip[1] - solve(thrust.start).hip[1]).toBeGreaterThan(20)
  expect(figureFor('glute-bridge', 'Single leg, on the floor')!.start.legF.at![1]).toBeGreaterThan(
    50,
  )
})
