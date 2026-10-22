import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Coverage, MuscleCoverage } from '../api'
import { BodyMap } from './BodyMap'
import { BACK, FRONT } from './regions'
import { amount, goal, sessionWarnings, warnings } from './words'

const muscle = (over: Partial<MuscleCoverage>): MuscleCoverage => ({
  muscle: 'quads',
  main: true,
  sets: 0,
  days: 0,
  most: 0,
  most_in: null,
  band: 'grey',
  low: 10,
  high: 20,
  evidence: null,
  one_day: false,
  over_session_cap: false,
  back_to_back: [],
  missing_parts: [],
  sources: [],
  ...over,
})

const glutes = muscle({
  muscle: 'glutes',
  sets: 12.5,
  days: 1,
  most: 11.5,
  most_in: 'Legs',
  band: 'light green',
  one_day: true,
  over_session_cap: true,
  sources: [
    { session: 'Legs', exercise: 'Pistol squat', sets: 3, weight: 1 },
    { session: 'Legs', exercise: 'Kettlebell swing', sets: 3, weight: 0.5 },
  ],
})
const lats = muscle({ muscle: 'lats', sets: 10, days: 2, most: 7, most_in: 'Torso', band: 'green' })
const neck = muscle({
  muscle: 'neck',
  main: false,
  sets: 7,
  days: 2,
  band: 'green',
  low: 3,
  high: 9,
  evidence: 'low',
})
const tibialis = muscle({
  muscle: 'tibialis',
  main: false,
  sets: 3,
  days: 1,
  band: 'green',
  low: 2,
  high: 6,
  evidence: 'very low',
})

const coverage: Coverage = {
  muscles: [glutes, lats, neck, tibialis],
  sessions: [
    { session: 'Legs', spine_sets: 10, grip_sets: 3, spine_heavy: true, grip_heavy: false },
    { session: 'Arms', spine_sets: 0, grip_sets: 9, spine_heavy: false, grip_heavy: true },
  ],
  main_on_target: 1,
  main_total: 10,
  session_cap: 11,
  back_to_back: 4,
  spine_cap: 8,
  grip_cap: 8,
  minimum: 4,
  ceiling: 30,
}

function answer(response: Partial<Response>) {
  globalThis.fetch = vi.fn().mockResolvedValue(response)
}

afterEach(() => vi.restoreAllMocks())

describe('BodyMap', () => {
  it('colours each muscle and lists them with their bands', async () => {
    answer({ ok: true, json: () => Promise.resolve(coverage) })
    const { container } = render(<BodyMap />)
    expect(await screen.findByText('1 of 10 main muscles on target')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /1 of 10 main muscles on target/ })).toBeInTheDocument()
    const region = container.querySelector('path[data-muscle="lats"]')
    expect(region).toHaveAttribute('fill', 'var(--band-green)')
    expect(container.querySelector('path[data-muscle="glutes"]')).toHaveAttribute(
      'fill',
      'var(--band-light-green)',
    )
    expect(container.querySelector('path[data-muscle="chest"]')).toHaveAttribute(
      'fill',
      'var(--band-grey)', // not in the answer: untrained
    )
    expect(screen.getByText('Legs: 10 spine-loading sets, over 8 in one session.')).toBeVisible()
    expect(screen.getByText(/Arms: 9 grip-heavy sets/)).toBeVisible()
    expect(
      screen.getByRole('button', { name: 'Glutes: 12.5 sets, Minimum, has a warning' }),
    ).toBeVisible()
  })

  it('opens a muscle to show where its sets come from', async () => {
    answer({ ok: true, json: () => Promise.resolve(coverage) })
    render(<BodyMap />)
    const row = await screen.findByRole('button', { name: /Glutes/, expanded: false })
    fireEvent.click(row)
    expect(row).toHaveAttribute('aria-expanded', 'true')
    const detail = row.parentElement!
    expect(within(detail).getByText('12.5 sets a week on 1 day.')).toBeVisible()
    expect(within(detail).getByText('Legs · Kettlebell swing: 3 × 0.5 = 1.5')).toBeVisible()
    expect(
      within(detail).getByText('Enough sets, but on one day: green needs two days a week.'),
    ).toBeVisible()
    fireEvent.click(row)
    expect(row).toHaveAttribute('aria-expanded', 'false')
  })

  it('tapping a region opens its row', async () => {
    answer({ ok: true, json: () => Promise.resolve(coverage) })
    Element.prototype.scrollIntoView = vi.fn()
    const { container } = render(<BodyMap />)
    await screen.findByText('1 of 10 main muscles on target')
    fireEvent.click(container.querySelector('path[data-muscle="neck"]')!)
    expect(
      screen.getByRole('button', { name: 'Neck: 7 sets, On target', expanded: true }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Low evidence for this band/)).toBeVisible()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    expect(container.querySelector('path[data-muscle="neck"]')).toHaveAttribute('stroke-width', '2')
  })

  it('marks very low evidence', async () => {
    answer({ ok: true, json: () => Promise.resolve(coverage) })
    render(<BodyMap />)
    fireEvent.click(await screen.findByRole('button', { name: /Tibialis/ }))
    expect(screen.getByText(/Very low evidence for this band/)).toBeVisible()
  })

  it('shows nothing when signed out, and explains a failed load', async () => {
    answer({ ok: false, status: 401 })
    const { container } = render(<BodyMap />)
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
    answer({ ok: false, status: 500 })
    render(<BodyMap />)
    expect(await screen.findByRole('alert')).toHaveTextContent('The server answered 500.')
  })
})

describe('words', () => {
  it('says how much, against which band', () => {
    expect(amount(muscle({}))).toBe('Not trained this week')
    expect(amount(muscle({ sets: 1, days: 1 }))).toBe('1 set a week on 1 day')
    expect(amount(lats)).toBe('10 sets a week on 2 days')
    expect(goal(lats)).toBe('Green: 10–20 sets on two days')
    expect(goal(neck)).toBe('Green: 3–9 sets')
  })

  it('words every warning', () => {
    const over = muscle({
      muscle: 'triceps',
      band: 'warning',
      sets: 31,
      one_day: true,
      back_to_back: ['Torso', 'Arms'],
      missing_parts: ['triceps long head', 'rectus femoris', 'something'],
    })
    expect(warnings(over, coverage)).toEqual([
      'Over 30 sets a week: more showed no extra growth.',
      'Trained on one day a week: green needs two.',
      '4+ sets in Torso and again in Arms, two days running: little rest between. A rule of thumb, not a study.',
      'Nothing reaches the triceps long head: it needs an overhead extension.',
      'Nothing reaches the rectus femoris (front of the thigh): it needs a leg extension.',
      'Nothing reaches the something.',
    ])
    expect(warnings(glutes, coverage)[0]).toBe(
      '11.5 sets in Legs: more than 11 in one session adds little.',
    )
    expect(warnings(lats, coverage)).toEqual([])
    expect(sessionWarnings({ ...coverage, sessions: [] })).toEqual([])
  })
})

describe('regions', () => {
  it('draws every muscle in the catalogue on a figure', () => {
    const drawn = new Set([...FRONT, ...BACK].map((r) => r.muscle))
    expect([...drawn].sort()).toEqual(
      [
        'abs',
        'adductors',
        'biceps',
        'calves',
        'chest',
        'forearms',
        'front delts',
        'glutes',
        'hamstrings',
        'hip flexors',
        'lats',
        'lower back',
        'neck',
        'obliques',
        'quads',
        'rear delts',
        'side delts',
        'tibialis',
        'triceps',
        'upper back',
        'upper traps',
      ].sort(),
    )
  })
})
