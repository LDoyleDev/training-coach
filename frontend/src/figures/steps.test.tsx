import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import plan from '../../../backend/src/training_coach/seed/plan.toml?raw'
import { BODY, blend, dist, solve } from './body'
import Figure from './Figure'
import { FIGURES } from './poses'
import { shapes, type Shape } from './shapes'
import { STEPS, figureFor } from './steps'

const ALONG = [0, 0.25, 0.5, 0.75, 1]

/** The ladder of ``slug`` in plan.toml. */
function ladder(slug: string): string[] {
  const blocks = plan.split('[[exercises]]')
  const block = blocks.find((b) => b.includes(`slug = "${slug}"\n`) && b.includes('ladder = '))
  const line = (block ?? '').split('\n').find((l) => l.startsWith('ladder = ')) ?? 'ladder = []'
  return JSON.parse(line.slice('ladder = '.length)) as string[]
}

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
  const loaded = figureFor('pull-up', 'Vest or backpack, 10 kg')!
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
  const pull = figureFor('pull-up', 'Vest or backpack, 5 kg')!
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
        expect(leg.knee[1] - 5.4, `${step}: knee off the floor`).toBeGreaterThan(5)
        expect(Math.min(leg.heel[1], leg.ball[1], leg.tip[1]), 'feet off').toBeGreaterThan(20)
        expect(leg.ankle[0], 'feet behind the knees').toBeLessThan(leg.knee[0] - 25)
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
