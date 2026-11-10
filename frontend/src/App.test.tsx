import { fireEvent, render, screen, within } from '@testing-library/react'
import App from './App'
import {
  prescription,
  sessionAt,
  sessionSize,
  type Coverage,
  type Exercise,
  type Place,
  type Plan,
  type Session,
} from './api'

const pullUp: Exercise = {
  slug: 'pull-up',
  name: 'Pull-up',
  kind: 'reps',
  sets: 4,
  rep_min: 5,
  rep_max: 12,
  per_side: false,
  muscles: { lats: 1, biceps: 0.5 },
  qualities: [],
  pattern: 'vertical pull',
  ladder: ['Slow negatives', 'Strict pull-up', 'Pause at top'],
  start_step: 1,
}

const latPulldown: Exercise = {
  ...pullUp,
  slug: 'lat-pulldown',
  name: 'Lat pulldown',
  sets: 3,
  rep_min: 8,
  ladder: ['Cable'],
  start_step: 0,
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
  gym: [latPulldown, { ...latPulldown, slug: 'face-pull', name: 'Face pull' }],
}

const zone2: Session = {
  position: 1,
  slug: 'zone2',
  name: 'Long zone 2',
  focus: 'Conversational pace',
  type: 'conditioning',
  optional: false,
  total_sets: 1,
  gym: [],
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

const coverage: Coverage = {
  place: 'home',
  places: 'home',
  muscles: [],
  sessions: [
    {
      session: 'Torso + neck',
      slug: 'torso',
      place: 'home',
      spine_sets: 0,
      grip_sets: 4,
      minutes: 40,
      over_an_hour: false,
      spine_heavy: false,
      grip_heavy: false,
      muscles: [{ muscle: 'lats', sets: 8, heat: 'hard' }],
    },
  ],
  main_on_target: 0,
  main_total: 10,
  session_cap: 11,
  back_to_back: 4,
  spine_cap: 8,
  grip_cap: 8,
  push_sets: 0,
  pull_sets: 0,
  pushing_without_pulling: false,
  hard_from: 6,
  minimum: 4,
  ceiling: 30,
}

/** The plan answers ``response``; the body map has its own tests and stays out of the way. */
function mockFetch(response: Partial<Response>) {
  globalThis.fetch = vi.fn((url: string) =>
    Promise.resolve(url === '/api/plan/coverage' ? { ok: false, status: 401 } : response),
  ) as unknown as typeof fetch
}

describe('App', () => {
  it('renders the week once the plan loads', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve(plan) })
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'Two sessions, one fixed order' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Strength and conditioning: each exercise at the step you're on, moving up as you go.",
      ),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('list', { name: 'Kinds of session' }))
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Strength', 'Conditioning'])
    expect(
      screen.getByRole('button', { name: /Torso \+ neck/, expanded: false }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'What the week gives each muscle' }),
    ).toBeInTheDocument()
  })

  it("reads the hero from a member's plan: a starter's sessions, all strength", async () => {
    const day = (position: number, name: string): Session => ({
      ...torso,
      position,
      slug: name,
      name,
    })
    mockFetch({
      ok: true,
      json: () =>
        Promise.resolve({
          ...plan,
          sessions: [day(0, 'Full body A'), day(1, 'Full body B'), day(2, 'Full body C')],
        }),
    })
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'Three sessions, one fixed order' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText("Strength: each exercise at the step you're on, moving up as you go."),
    ).toBeInTheDocument()
    expect(screen.queryByText(/kettlebell/)).not.toBeInTheDocument()
  })

  it("shows the ladders of a member's own plan: a starter's exercises", async () => {
    const ex = (slug: string, name: string, steps = 3): Exercise => ({
      ...pullUp,
      slug,
      name,
      ladder: ['Easy', 'Middle', 'Hard'].slice(0, steps),
      start_step: 0,
    })
    const a = {
      ...torso,
      name: 'Full body A',
      slug: 'a',
      exercises: [
        ex('goblet-squat', 'Goblet squat'),
        ex('doorway-row', 'Doorway row'),
        ex('push-up', 'Push-up'),
        ex('band-pull-apart', 'Band pull-apart', 1),
      ],
    }
    const b = {
      ...torso,
      position: 1,
      name: 'Full body B',
      slug: 'b',
      exercises: [
        ex('bulgarian-split-squat', 'Bulgarian split squat'),
        ex('push-up', 'Push-up'),
        ex('glute-bridge', 'Glute bridge'),
        ex('plank', 'Plank'),
      ],
    }
    mockFetch({ ok: true, json: () => Promise.resolve({ ...plan, sessions: [a, b, zone2] }) })
    render(<App />)
    const ladders = await screen.findByRole('region', { name: 'Harder without heavier weights' })
    expect(
      within(ladders)
        .getAllByRole('heading', { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(['Push-up', 'Bulgarian split squat', 'Goblet squat', 'Doorway row', 'Glute bridge'])
  })

  it("shows the owner's five ladders when his plan has them, whatever else it has", async () => {
    const ex = (slug: string, name: string): Exercise => ({ ...pullUp, slug, name })
    const legs = {
      ...torso,
      position: 1,
      name: 'Legs',
      slug: 'legs',
      exercises: [
        ex('kb-swing', 'Kettlebell swing'),
        ex('hamstring-curl', 'Hamstring curl'),
        ex('pistol-squat', 'Pistol squat'),
        ex('bulgarian-split-squat', 'Bulgarian split squat'),
      ],
    }
    const upper = { ...torso, exercises: [ex('dip', 'Dip'), ex('push-up', 'Push-up'), pullUp] }
    mockFetch({ ok: true, json: () => Promise.resolve({ ...plan, sessions: [legs, upper] }) })
    render(<App />)
    const ladders = await screen.findByRole('region', { name: 'Harder without heavier weights' })
    expect(
      within(ladders)
        .getAllByRole('heading', { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(['Pull-up', 'Push-up', 'Bulgarian split squat', 'Pistol squat', 'Hamstring curl'])
  })

  it('a plan without strength work just names its kinds', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve({ ...plan, sessions: [zone2] }) })
    render(<App />)
    expect(await screen.findByText('Conditioning.')).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Harder without heavier weights' }),
    ).not.toBeInTheDocument()
  })

  it('says a plan with no sessions plainly', async () => {
    mockFetch({ ok: true, json: () => Promise.resolve({ ...plan, sessions: [] }) })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'No sessions yet' })).toBeInTheDocument()
    expect(screen.queryByText(/^: each exercise/)).not.toBeInTheDocument()
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

  it("an open session shows its own body map first, and the week's comes last", async () => {
    globalThis.fetch = vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(url === '/api/plan/coverage' ? coverage : plan),
      }),
    ) as unknown as typeof fetch
    const { container } = render(<App />)
    const row = await screen.findByRole('button', { name: /Torso \+ neck/, expanded: false })
    fireEvent.click(row)
    const panel = document.getElementById('session-torso')!
    expect(
      await within(panel).findByRole('img', { name: /What Torso \+ neck works: hardest on Lats/ }),
    ).toBeVisible()
    expect(panel.querySelector('path[data-muscle="lats"]')).toHaveAttribute(
      'fill',
      'var(--heat-hard)',
    )
    const headings = [...container.querySelectorAll('h2')].map((h) => h.textContent)
    expect(headings.at(-1)).toBe('What the week gives each muscle')
    expect(
      vi.mocked(globalThis.fetch).mock.calls.filter(([u]) => u === '/api/plan/coverage'),
    ).toHaveLength(1)
    expect(screen.queryByRole('group', { name: 'Count the sessions at' })).not.toBeInTheDocument()
  })

  it('counts the home or gym versions for someone who trains at both', async () => {
    const at = (place: Place): Coverage => ({
      ...coverage,
      place,
      places: 'both',
      main_on_target: place === 'gym' ? 9 : 10,
      sessions: [
        {
          ...coverage.sessions[0],
          place,
          muscles: [{ muscle: 'lats', sets: place === 'gym' ? 10 : 8, heat: 'hard' }],
        },
      ],
    })
    globalThis.fetch = vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(url === '/api/plan' ? plan : at(url.endsWith('=gym') ? 'gym' : 'home')),
      }),
    ) as unknown as typeof fetch
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Torso \+ neck/, expanded: false }))
    const week = screen.getByRole('region', { name: 'The week' })
    const total = screen.getByRole('region', { name: 'What the week gives each muscle' })
    const panel = document.getElementById('session-torso')!
    expect(await within(week).findByRole('button', { name: 'Home', pressed: true })).toBeVisible()
    expect(within(total).getByText('10 of 10 main muscles on target')).toBeVisible()
    expect(within(panel).getByRole('rowheader', { name: 'Pull-up' })).toBeVisible()
    expect(within(week).getByRole('button', { name: /Torso \+ neck/ })).toHaveTextContent('4 sets')
    fireEvent.click(within(total).getByRole('button', { name: 'Gym' }))
    expect(await within(total).findByText('9 of 10 main muscles on target')).toBeVisible()
    expect(within(total).getByText(/The whole week at the gym/)).toBeVisible()
    expect(within(week).getByRole('button', { name: 'Gym', pressed: true })).toBeVisible()
    expect(within(panel).getByRole('button', { name: /Lats: 10 sets/ })).toBeVisible()
    expect(within(panel).getByText('What its gym version works.')).toBeVisible()
    expect(
      within(panel)
        .getAllByRole('rowheader')
        .map((h) => h.textContent),
    ).toEqual(['Lat pulldown', 'Face pull'])
    expect(within(panel).getAllByRole('cell')[0]).toHaveTextContent('3 × 8–12')
    expect(within(week).getByRole('button', { name: /Torso \+ neck/ })).toHaveTextContent('6 sets')
    expect(vi.mocked(globalThis.fetch)).toHaveBeenCalledWith(
      '/api/plan/coverage?place=gym',
      expect.anything(),
    )
  })

  it('at the gym only, lists the gym versions, and a session without one keeps its own', async () => {
    const gym: Coverage = {
      ...coverage,
      place: 'gym',
      places: 'gym',
      sessions: [
        { ...coverage.sessions[0], place: 'gym' },
        { ...coverage.sessions[0], session: 'Long zone 2', slug: 'zone2', muscles: [] },
      ],
    }
    globalThis.fetch = vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(url === '/api/plan' ? plan : gym),
      }),
    ) as unknown as typeof fetch
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Torso \+ neck/, expanded: false }))
    const torsoPanel = document.getElementById('session-torso')!
    expect(await within(torsoPanel).findByRole('rowheader', { name: 'Lat pulldown' })).toBeVisible()
    expect(within(torsoPanel).queryByRole('rowheader', { name: 'Pull-up' })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Count the sessions at' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Long zone 2/, expanded: false }))
    const zone2Panel = document.getElementById('session-zone2')!
    expect(within(zone2Panel).getByRole('rowheader', { name: 'Zone 2' })).toBeVisible()
  })

  it('keeps the maps when the other view fails to load, and tries again on a tap', async () => {
    const both = { ...coverage, places: 'both' } as Coverage
    let down = true
    globalThis.fetch = vi.fn((url: string) =>
      Promise.resolve(
        url === '/api/plan'
          ? { ok: true, json: () => Promise.resolve(plan) }
          : url === '/api/plan/coverage' || !down
            ? {
                ok: true,
                json: () =>
                  Promise.resolve({ ...both, place: url.endsWith('=gym') ? 'gym' : 'home' }),
              }
            : { ok: false, status: 503 },
      ),
    ) as unknown as typeof fetch
    render(<App />)
    const total = await screen.findByRole('region', { name: 'What the week gives each muscle' })
    fireEvent.click(await within(total).findByRole('button', { name: 'Gym' }))
    expect(await within(total).findByRole('alert')).toHaveTextContent(
      "Couldn't load the gym view. The server answered 503. Try again.",
    )
    expect(within(total).getByRole('button', { name: 'Home', pressed: true })).toBeVisible()
    expect(within(total).getByText('0 of 10 main muscles on target')).toBeVisible()
    down = false
    fireEvent.click(within(total).getByRole('button', { name: 'Gym' }))
    expect(await within(total).findByRole('button', { name: 'Gym', pressed: true })).toBeVisible()
    expect(within(total).queryByRole('alert')).not.toBeInTheDocument()
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
  it("takes a session's gym version at the gym, and its one version without one", () => {
    expect(sessionAt(torso, 'home')).toBe(torso)
    expect(sessionAt(torso, 'gym')).toMatchObject({ exercises: torso.gym, total_sets: 6 })
    expect(sessionAt(zone2, 'gym')).toBe(zone2)
  })

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
