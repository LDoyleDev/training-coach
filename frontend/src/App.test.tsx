import { fireEvent, render, screen } from '@testing-library/react'
import App from './App'
import { prescription, sessionSize, type Exercise, type Plan, type Session } from './api'

const pullUp: Exercise = {
  slug: 'pull-up',
  name: 'Pull-up',
  kind: 'reps',
  sets: 4,
  rep_min: 5,
  rep_max: 12,
  per_side: false,
  muscle_groups: ['lats'],
  ladder: ['Slow negatives', 'Strict pull-up', 'Pause at top'],
  start_step: 1,
}

const torso: Session = {
  position: 0,
  slug: 'torso',
  name: 'Torso + neck',
  focus: 'Back, chest, shoulders, neck',
  type: 'strength',
  optional: false,
  total_sets: 4,
  exercises: [pullUp],
}

const zone2: Session = {
  position: 1,
  slug: 'zone2',
  name: 'Long zone 2',
  focus: 'Conversational pace',
  type: 'conditioning',
  optional: false,
  total_sets: 1,
  exercises: [
    {
      ...pullUp,
      slug: 'zone2',
      name: 'Zone 2',
      kind: 'duration_min',
      sets: 1,
      rep_min: 45,
      rep_max: 75,
      ladder: ['Walk'],
      start_step: 0,
    },
  ],
}

const plan: Plan = {
  sessions: [torso, zone2],
  volume: [{ group: 'lats', sets: 12 }],
  volume_target_min: 10,
  volume_target_max: 20,
}

function mockFetch(response: Partial<Response>) {
  globalThis.fetch = vi.fn().mockResolvedValue(response)
}

describe('App', () => {
  it('renders the week once the plan loads', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve(plan) })
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'Seven sessions, one fixed order' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Torso \+ neck/, expanded: false }),
    ).toBeInTheDocument()
    expect(screen.getByText('Lats')).toBeInTheDocument()
  })

  it('links to the signed-in app', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve(plan) })
    render(<App />)
    expect(await screen.findByRole('link', { name: 'Today' })).toHaveAttribute('href', '/session')
  })

  it('opens a session to show its exercises', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve(plan) })
    render(<App />)
    const row = await screen.findByRole('button', { name: /Torso \+ neck/, expanded: false })
    expect(row).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(row)
    expect(row).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('rowheader', { name: 'Pull-up' })).toBeVisible()
  })

  it('selecting a ring segment opens that session', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve(plan) })
    Element.prototype.scrollIntoView = vi.fn()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '2. Long zone 2' }))
    expect(screen.getByRole('button', { name: /Long zone 2/, expanded: true })).toBeInTheDocument()
  })

  it('asks to sign in when signed out', async () => {
    mockFetch({ ok: false, status: 401, json: () => Promise.resolve({}) })
    render(<App />)
    expect(await screen.findByRole('link', { name: 'Sign in' })).toHaveAttribute(
      'href',
      '/signin?next=/plan',
    )
  })

  it('explains a failed load', async () => {
    mockFetch({ ok: false, status: 503 })
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('The server answered 503.')
  })
})

describe('formatting', () => {
  it('describes sets, ranges and sides', () => {
    expect(prescription(pullUp)).toBe('4 × 5–12')
    expect(prescription({ ...pullUp, per_side: true, rep_min: 8, rep_max: 8 })).toBe(
      '4 × 8 per side',
    )
    expect(
      prescription({ ...pullUp, sets: 1, kind: 'duration_min', rep_min: 30, rep_max: 40 }),
    ).toBe('30–40 min')
    expect(prescription({ ...pullUp, sets: 2, kind: 'seconds', rep_min: 30, rep_max: 60 })).toBe(
      '2 × 30–60 s',
    )
  })

  it('sizes sessions in sets or minutes', () => {
    expect(sessionSize(torso)).toBe('4 sets')
    expect(sessionSize(zone2)).toBe('45–75 min')
    expect(sessionSize({ ...zone2, exercises: [{ ...pullUp, rep_min: 8 }] })).toBe('8+ rounds')
  })
})
