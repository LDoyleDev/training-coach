import { expect, test } from 'vitest'
import { BODY, blend, dist, heading, solve, type Joints } from './body'
import { solveFront, type FrontJoints } from './front'
import { AWAY } from './away'
import { FIGURES } from './poses'
import { figureFor } from './steps'

const ALONG = [0, 0.25, 0.5, 0.75, 1]
const poses = (slug: string, step?: string): Joints[] => {
  const f = figureFor(slug, step)!
  return ALONG.map((t) => solve(blend(f.start, f.end, t)))
}
const fronts = (step?: string): FrontJoints[] => {
  const { front } = figureFor('doorway-curl', step)!
  return ALONG.map((t) => solveFront(blend(front!.start, front!.end, t)))
}
const ROWS = [
  undefined,
  'Upright, a step back',
  'Leaning back, half a step in',
  'One arm, feet at the frame',
]

test('the door-frame pulls are figures', () => {
  for (const slug of Object.keys(AWAY)) expect(FIGURES[slug], slug).toBe(AWAY[slug])
})

test('a door-frame row holds the frame, heels down, the body straight from heels to head', () => {
  const frame = FIGURES['doorway-row'].props!.wall!.x0
  const heels: number[] = []
  for (const step of ROWS) {
    const all = poses('doorway-row', step)
    for (const j of all) {
      expect(j.armN.wrist[0] - frame, `${step}: hand on the frame`).toBeCloseTo(-2, 1)
      expect(j.legN.heel[1], `${step}: heels down`).toBeCloseTo(1.5, 0)
      expect(j.legN.heel[0]).toBeCloseTo(all[0].legN.heel[0], 5)
      const line = Math.abs(heading(j.legN.ankle, j.hip) - heading(j.hip, j.shoulder))
      expect(line, `${step}: straight`).toBeLessThan(1)
    }
    const [out, inn] = [all[0], all[4]]
    expect(dist(out.shoulder, out.armN.wrist), `${step}: arms straight`).toBeGreaterThan(53)
    expect(dist(inn.shoulder, inn.armN.wrist), `${step}: pulled in`).toBeLessThan(36)
    expect(inn.shoulder[0], `${step}: towards the frame`).toBeGreaterThan(out.shoulder[0])
    heels.push(out.legN.heel[0])
  }
  // Toes level with the frame for the figure; a step back and half a step in stand further off.
  expect(heels[0]).toBeGreaterThan(heels[2])
  expect(heels[2]).toBeGreaterThan(heels[1])
  // One arm: the other hangs at your side.
  const one = poses('doorway-row', 'One arm, feet at the frame')[0]
  expect(one.armF.wrist[1]).toBeLessThan(one.hip[1])
})

test('a door-frame curl is seen from the front only: the hand stays on the frame', () => {
  for (const step of [undefined, 'Leaning back a little']) {
    const { front } = figureFor('doorway-curl', step)!
    expect(front!.only, `${step}`).toBe(true)
    const all = fronts(step)
    for (const j of all) {
      expect(dist(j.armL.end, all[0].armL.end), `${step}: hand on the frame`).toBeLessThan(0.1)
      for (const leg of [j.legL, j.legR]) expect(leg.end[1], `${step}: feet down`).toBeCloseTo(7, 1)
      expect(dist(j.armL.root, j.armL.mid)).toBeLessThan(BODY.upperArm + 0.05)
      expect(dist(j.armL.mid, j.armL.end)).toBeLessThan(BODY.forearm + 0.05)
    }
    const [hanging, curled] = [all[0], all[4]]
    expect(dist(hanging.armL.root, hanging.armL.end), `${step}: arm straight`).toBeGreaterThan(54)
    expect(dist(curled.armL.root, curled.armL.end), `${step}: curled`).toBeLessThan(40)
    expect(curled.armL.mid[1], `${step}: elbow down at the side`).toBeLessThan(
      curled.armL.root[1] - 15,
    )
    // Leaning away from the frame, then back towards upright.
    expect(Math.abs(curled.waist[0] - curled.hip[0])).toBeLessThan(
      Math.abs(hanging.waist[0] - hanging.hip[0]),
    )
  }
  const lean = (step?: string) => figureFor('doorway-curl', step)!.front!.start.tilt
  expect(lean('Leaning back a little'), 'a little').toBeLessThan(lean())
})
