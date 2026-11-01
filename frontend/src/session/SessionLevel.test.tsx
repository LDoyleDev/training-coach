import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Guided, GuidedItem, Kept, LevelChanged, Saved, TodayView } from '../api'
import SessionPage from './SessionPage'

vi.mock('../hiit/sounds', () => ({
  DEFAULT_SOUND: 'ring',
  unlockAudio: vi.fn(),
  playChange: vi.fn(),
  playSessionEnd: vi.fn(),
}))

const LADDER = [
  { id: 20, name: 'Two-hand, 8 kg', cue: null, missing: [], avoided: [] },
  { id: 21, name: 'One-arm, 8 kg', cue: null, missing: [], avoided: [] },
  { id: 22, name: 'Two-hand, 16 kg', cue: null, missing: [], avoided: [] },
]

const SWING: GuidedItem = {
  slug: 'kb-swing',
  name: 'Kettlebell swing',
  step: 'Two-hand, 8 kg',
  summary: null,
  cue: null,
  unit: 'reps',
  per_side: false,
  pair: null,
  targets: [20, 20],
  baseline: false,
  muscles: [],
  parts: [],
  level: { step_id: 20, for_today: false, ladder: LADDER },
}

const session = (item: GuidedItem): Guided => ({
  day: '2026-10-27',
  template_id: 5,
  name: 'Legs',
  focus: 'Hinge',
  kind: 'strength',
  warm_up: false,
  block: null,
  minutes: 20,
  rest_seconds: 60,
  after_run: false,
  place: 'home',
  place_choice: false,
  ease_back: [],
  items: [item],
  order: item.targets.map((target, i) => ({
    item: 0,
    set_no: i + 1,
    target,
    rest_seconds: 60,
    switch: false,
  })),
})

const SIXTEEN: GuidedItem = {
  ...SWING,
  step: 'Two-hand, 16 kg',
  targets: [15, 15],
  baseline: true,
  level: { step_id: 22, for_today: true, ladder: LADDER },
}

const kept = (revision: number, sets: Kept['sets'] = []): Kept => ({
  template_id: 5,
  position: sets.length,
  first: [],
  sets,
  saved: false,
  revision,
})

const CHANGED: LevelChanged = {
  warning: null,
  today: { session: session(SIXTEEN), progress: kept(2) },
}

type Server = { today?: TodayView; level?: LevelChanged | 'stale' | 422 | 500; save?: Saved }

function serve(server: Server = {}) {
  const sent: Record<string, unknown[]> = {}
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      ;(sent[`${method} ${path}`] ??= []).push(init?.body ? JSON.parse(String(init.body)) : null)
      if (path === '/api/session/today')
        return Response.json(server.today ?? { session: session(SWING), progress: null })
      if (path === '/api/session/level') {
        const level = server.level ?? CHANGED
        if (typeof level === 'number') return new Response(null, { status: level })
        return level === 'stale' ? new Response(null, { status: 409 }) : Response.json(level)
      }
      if (path === '/api/session/progress') return Response.json({ revision: 3 })
      if (path === '/api/session/pending') return Response.json([])
      if (path === '/api/session/save') return Response.json(server.save)
      if (path === '/api/settings') return Response.json({ sound: 'ring', stop_signs_seen: true })
      return new Response(null, { status: 404 })
    }),
  )
  return sent
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  localStorage.clear()
})

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

async function onTheSetScreen() {
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('heading', { name: 'Kettlebell swing' })).toBeInTheDocument()
}

test('for today: the rest of the sets switch to the new step and its targets', async () => {
  const sent = serve()
  await onTheSetScreen()
  expect(screen.getByText('Target 20')).toBeInTheDocument()
  click('Change level')
  expect(screen.getAllByRole('radio')).toHaveLength(2) // one level up: none below the first
  click('All levels (3)')
  fireEvent.click(screen.getByRole('radio', { name: 'Two-hand, 16 kg' }))
  click('For today')
  expect(await screen.findByText('· for today only')).toBeInTheDocument()
  expect(screen.getByText('Two-hand, 16 kg')).toBeInTheDocument()
  expect(screen.getByText('Target 15')).toBeInTheDocument()
  expect(screen.getAllByText('Set 1 of 2')).toHaveLength(2) // still on this set
  expect(screen.getByRole('status')).toHaveTextContent(
    'Kettlebell swing: Two-hand, 16 kg for today. Your level stays as it was.',
  )
  expect(sent['PUT /api/session/level']).toEqual([
    { template_id: 5, revision: 0, first: [], slug: 'kb-swing', step_id: 22, scope: 'today' },
  ])
  click('Confirm set')
  await screen.findByRole('button', { name: 'Skip rest' })
  expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({ revision: 2 }) // the new one
})

test('from now on sends the level change as the person picked it', async () => {
  const sent = serve({
    level: {
      warning: 'Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit.',
      today: {
        session: session({ ...SIXTEEN, level: { ...SIXTEEN.level!, for_today: false } }),
        progress: kept(2),
      },
    },
  })
  await onTheSetScreen()
  click('Change level')
  expect(screen.getAllByRole('radio')).toHaveLength(2) // one level up: none below the first
  click('All levels (3)')
  fireEvent.click(screen.getByRole('radio', { name: 'Two-hand, 16 kg' }))
  click('From now on')
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Kettlebell swing is now on Two-hand, 16 kg, today and from now on.',
  )
  expect(screen.getByRole('status')).toHaveTextContent('needs a 16 kg kettlebell')
  expect(screen.queryByText('· for today only')).not.toBeInTheDocument()
  expect(sent['PUT /api/session/level']?.[0]).toMatchObject({ scope: 'from_now_on' })
})

test('a reload keeps a level chosen for today', async () => {
  const done = [{ item: 0, set_no: 1, left: 20, right: null }]
  serve({ today: { session: session(SIXTEEN), progress: kept(4, done) } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: /Resume|Start/ }))
  expect(screen.getByText('· for today only')).toBeInTheDocument()
  expect(screen.getAllByText('Set 2 of 2')).toHaveLength(2)
  click('Change level')
  fireEvent.click(screen.getByRole('radio', { name: 'One-arm, 8 kg' }))
  expect(screen.getByText('The set you’ve done stays at Two-hand, 16 kg.')).toBeInTheDocument()
})

test('a session changed elsewhere reloads instead of changing the level', async () => {
  const sent = serve({ level: 'stale' })
  await onTheSetScreen()
  click('Change level')
  fireEvent.click(screen.getByRole('radio', { name: 'One-arm, 8 kg' }))
  click('For today')
  expect(await screen.findByText(/Today's session changed/)).toBeInTheDocument()
  expect(sent['GET /api/session/today']).toHaveLength(2)
})

test.each([
  [422, "That step isn't on this exercise's ladder."],
  [500, "Couldn't change the level. Check your connection and try again."],
] as const)('a refused or failed change says why and changes nothing (%s)', async (code, text) => {
  serve({ level: code })
  await onTheSetScreen()
  click('Change level')
  fireEvent.click(screen.getByRole('radio', { name: 'One-arm, 8 kg' }))
  click('For today')
  expect(await screen.findByRole('status')).toHaveTextContent(text)
  expect(screen.getByRole('group', { name: 'Level for Kettlebell swing' })).toBeInTheDocument()
  expect(screen.getByText('Target 20')).toBeInTheDocument()
})

test('the saved screen says the steps the sets were done at', async () => {
  const done = [
    { item: 0, set_no: 1, left: 20, right: null },
    { item: 0, set_no: 2, left: 15, right: null },
  ]
  serve({
    today: { session: session(SIXTEEN), progress: kept(4, done) },
    save: {
      workout_id: 9,
      already_saved: false,
      next_session: null,
      earned: [],
      stretching: false,
      levels: [{ exercise: 'Kettlebell swing', steps: ['Two-hand, 8 kg', 'Two-hand, 16 kg'] }],
    },
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: /Check|Save|Resume|Start/ }))
  click('Save session')
  expect(
    await screen.findByText('Kettlebell swing done at Two-hand, 8 kg, then Two-hand, 16 kg.'),
  ).toBeInTheDocument()
})
