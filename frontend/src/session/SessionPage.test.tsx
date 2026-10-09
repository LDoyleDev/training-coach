import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Guided, Kept, Pending, Saved, TodayView } from '../api'
import SessionPage from './SessionPage'

const SESSION: Guided = {
  day: '2026-10-12',
  template_id: 3,
  name: 'Legs',
  focus: 'Quads, hamstrings',
  kind: 'strength',
  warm_up: true,
  block: null,
  minutes: 45,
  rest_seconds: 60,
  items: [
    {
      slug: 'jump-squat',
      name: 'Jump squat',
      step: 'Bodyweight',
      summary: 'Squat, then jump.',
      cue: null,
      unit: 'reps',
      per_side: false,
      pair: 1,
      targets: [6, 6],
      baseline: true,
    },
    {
      slug: 'calf-raise',
      name: 'Calf raise',
      step: 'On a step',
      summary: null,
      cue: null,
      unit: 'reps',
      per_side: true,
      pair: 1,
      targets: [15],
      baseline: false,
    },
  ],
  order: [
    { item: 0, set_no: 1, target: 6 },
    { item: 1, set_no: 1, target: 15 },
    { item: 0, set_no: 2, target: 6 },
  ],
}

const SAVED: Saved = {
  workout_id: 9,
  already_saved: false,
  next_session: 'Recovery + posture',
  earned: [{ exercise: 'Jump squat', unit: 'reps', best_set: 7, total: 13, next_step: null }],
  stretching: true,
}

type Server = {
  today?: TodayView | null | 'error'
  keep?: number | 'stale'
  save?: Saved | 'stale'
  pending?: Pending[]
  saveEarlier?: 'fail'
}

/** A fake API; returns the bodies sent, by method and path. */
function serve(server: Server = {}) {
  const sent: Record<string, unknown[]> = {}
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    ;(sent[`${method} ${path}`] ??= []).push(init?.body ? JSON.parse(String(init.body)) : null)
    if (path === '/api/session/today') {
      const today = server.today === undefined ? { session: SESSION, progress: null } : server.today
      if (today === 'error') return new Response(null, { status: 500 })
      if (today === null) return new Response(null, { status: 401 })
      return Response.json(today)
    }
    if (path === '/api/session/progress') {
      const keep = server.keep ?? 1
      return keep === 'stale'
        ? new Response(null, { status: 409 })
        : Response.json({ revision: keep })
    }
    if (path === '/api/session/pending') return Response.json(server.pending ?? [])
    if (path === '/api/session/save') {
      if (server.saveEarlier === 'fail' && init?.body !== '{}')
        return new Response(null, { status: 500 })
      const save = server.save ?? SAVED
      return save === 'stale' ? new Response(null, { status: 409 }) : Response.json(save)
    }
    return new Response(null, { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return sent
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

test('a whole session: overview, sets in pair order, check, save', async () => {
  const sent = serve()
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.getByText('Warm up for about 10 minutes first.')).toBeInTheDocument()
  click('Start session')

  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  expect(screen.getByText('PAIR 1 · ALTERNATE WITH CALF RAISE')).toBeInTheDocument()
  click('1 more')
  expect(screen.getByText('1 over')).toBeInTheDocument()
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))

  expect(await screen.findByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
  expect(screen.getByRole('group', { name: 'Each side' })).toBeInTheDocument()
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  expect(await screen.findByText('Set 2 of 2')).toBeInTheDocument()
  click('Confirm set')

  expect(await screen.findByRole('heading', { name: 'Check and save' })).toBeInTheDocument()
  expect(screen.getByText('7 · 6')).toBeInTheDocument()
  click('Save session')
  expect(await screen.findByRole('heading', { name: 'Legs done' })).toBeInTheDocument()
  expect(screen.getByText('Next up: Recovery + posture.')).toBeInTheDocument()
  expect(screen.getByText(/new best 7 in one set/)).toBeInTheDocument()

  const kept = sent['PUT /api/session/progress']
  expect(kept).toHaveLength(3)
  expect(kept[0]).toMatchObject({
    template_id: 3,
    revision: 0,
    position: 1,
    sets: [{ item: 0, set_no: 1, left: 7, right: null }],
  })
  expect(kept[2]).toMatchObject({ revision: 1, position: 3 })
})

test('left and right can differ on a one-sided exercise', async () => {
  const kept: Kept = { template_id: 3, position: 1, first: [], sets: [], saved: false, revision: 4 }
  const sent = serve({ today: { session: SESSION, progress: kept } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume: set 2 of 3' }))
  click('Left and right differ')
  const right = screen.getByRole('group', { name: 'Right' })
  fireEvent.click(right.querySelector('button[aria-label="1 fewer"]')!)
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  await waitFor(() => expect(screen.getByText('Set 3 of 3')).toBeInTheDocument())
  expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({
    revision: 4,
    sets: [{ item: 1, set_no: 1, left: 15, right: 14 }],
  })
})

test('resuming starts at the kept set with the kept values', async () => {
  const progress: Kept = {
    template_id: 3,
    position: 1,
    first: [],
    sets: [{ item: 0, set_no: 1, left: 8, right: null }],
    saved: false,
    revision: 2,
  }
  const sent = serve({ today: { session: SESSION, progress } })
  render(<SessionPage />)
  click(await screen.findByText('Resume: set 2 of 3').then(() => 'Resume: set 2 of 3'))
  expect(screen.getByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
  click('Back')
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  expect(screen.getByText('8')).toBeInTheDocument()
  click('Confirm set')
  await waitFor(() => expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({ revision: 2 }))
})

test('another device having moved on reloads instead of overwriting', async () => {
  const sent = serve({ keep: 'stale' })
  render(<SessionPage />)
  click(await screen.findByText('Start session').then(() => 'Start session'))
  click('Confirm set')
  expect(await screen.findByText(/moved on from another device/)).toBeInTheDocument()
  await waitFor(() => expect(sent['GET /api/session/today']).toHaveLength(2))
})

test('leaving goes back to the overview', async () => {
  serve()
  render(<SessionPage />)
  click(await screen.findByText('Start session').then(() => 'Start session'))
  click('Leave')
  expect(screen.getByRole('heading', { name: 'Legs' })).toBeInTheDocument()
})

test('a save refused because today changed says so', async () => {
  serve({ save: 'stale' })
  const progress: Kept = {
    template_id: 3,
    position: 3,
    first: [],
    sets: [
      { item: 0, set_no: 1, left: 6, right: null },
      { item: 1, set_no: 1, left: 15, right: 12 },
      { item: 0, set_no: 2, left: 6, right: null },
    ],
    saved: false,
    revision: 3,
  }
  serve({ today: { session: SESSION, progress }, save: 'stale' })
  render(<SessionPage />)
  click(await screen.findByText('Start session').then(() => 'Start session'))
  expect(screen.getByText('15/12')).toBeInTheDocument()
  click('Save session')
  expect(await screen.findByText(/Today's session changed/)).toBeInTheDocument()
  click('Back')
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  expect(screen.queryByText(/Today's session changed/)).not.toBeInTheDocument()
})

test.each([
  [null, /Sign in to start today's session/],
  [{ session: null, progress: null }, /Nothing left to train today/],
  [{ session: { ...SESSION, order: [] }, progress: null }, /Nothing left to train today/],
  ['error' as const, /Couldn't load today's session/],
])('states without a session: %s', async (today, text) => {
  serve({ today })
  render(<SessionPage />)
  expect(await screen.findByText(text)).toBeInTheDocument()
})

test('fixing an earlier set returns to the furthest set, and the server keeps it', async () => {
  const progress: Kept = {
    template_id: 3,
    position: 2,
    first: [],
    sets: [
      { item: 0, set_no: 1, left: 6, right: null },
      { item: 1, set_no: 1, left: 15, right: null },
    ],
    saved: false,
    revision: 5,
  }
  const sent = serve({ today: { session: SESSION, progress } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume: set 3 of 3' }))
  click('Back')
  click('Back')
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  click('1 fewer')
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  expect(await screen.findByText('Set 3 of 3')).toBeInTheDocument()
  expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({ position: 2 })
  click('Leave')
  expect(screen.getByRole('button', { name: 'Resume: set 3 of 3' })).toBeInTheDocument()
})

test('the rest counts down, can be lengthened, and buzzes into the next set', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const vibrate = vi.fn()
  vi.stubGlobal('navigator', { ...navigator, vibrate })
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Confirm set')
  expect(await screen.findByText('1:00')).toBeInTheDocument()
  expect(screen.getByText('Calf raise')).toBeInTheDocument() // next
  click('+ 15 s')
  expect(screen.getByText('1:15')).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(75_000))
  expect(await screen.findByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
  expect(vibrate).toHaveBeenCalledWith(300)
})

test('a timed set uses a stopwatch, then plus and minus by 5 seconds', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const hang: Guided = {
    ...SESSION,
    items: [
      {
        ...SESSION.items[0],
        slug: 'dead-hang',
        name: 'Dead hang',
        unit: 'seconds',
        pair: null,
        targets: [30],
      },
    ],
    order: [{ item: 0, set_no: 1, target: 30 }],
  }
  const sent = serve({ today: { session: hang, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Start clock')
  act(() => vi.advanceTimersByTime(42_000))
  click('Stop')
  expect(screen.getByText('42 s')).toBeInTheDocument()
  click('5 more')
  click('Confirm set')
  await screen.findByRole('heading', { name: 'Check and save' })
  expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({
    sets: [{ item: 0, set_no: 1, left: 47, right: null }],
  })
})

test('a pair can start with its second exercise before it has begun', async () => {
  const sent = serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Do Calf raise first')
  await waitFor(() => expect(sent['GET /api/session/today']).toHaveLength(2))
  expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({ first: [1], position: 0 })
})

test("an earlier day's unsaved session can be saved from the overview", async () => {
  const sent = serve({ pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }] })
  render(<SessionPage />)
  expect(
    await screen.findByText(/Torso \+ neck on 2026-10-11 wasn't saved \(5 sets\)/),
  ).toBeInTheDocument()
  click('Save it')
  expect(await screen.findByText('Saved Torso + neck for 2026-10-11.')).toBeInTheDocument()
  expect(sent['POST /api/session/save']?.[0]).toEqual({ day: '2026-10-11' })
  expect(screen.queryByRole('button', { name: 'Save it' })).not.toBeInTheDocument()
})

test('a failed save of an earlier day keeps it offered', async () => {
  serve({ pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }], saveEarlier: 'fail' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save it' }))
  expect(await screen.findByText(/Check your connection/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save it' })).toBeInTheDocument()
})

test('leaving stops a running clock', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const hang: Guided = {
    ...SESSION,
    items: [{ ...SESSION.items[0], name: 'Dead hang', unit: 'seconds', pair: null, targets: [30] }],
    order: [{ item: 0, set_no: 1, target: 30 }],
  }
  serve({ today: { session: hang, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Start clock')
  act(() => vi.advanceTimersByTime(5_000))
  click('Leave')
  fireEvent.click(screen.getByRole('button', { name: 'Start session' }))
  expect(screen.getByText('30 s')).toBeInTheDocument() // the target again, not a running clock
  expect(screen.getByRole('button', { name: 'Start clock' })).toBeInTheDocument()
})

const HANG: Guided = {
  ...SESSION,
  items: [{ ...SESSION.items[0], name: 'Dead hang', unit: 'seconds', pair: null, targets: [30] }],
  order: [{ item: 0, set_no: 1, target: 30 }],
}

test('the stopwatch keeps time while the screen is locked', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  serve({ today: { session: HANG, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Start clock')
  // Locked: the clock moves on but no timer fires; unlocking reads the time again.
  act(() => {
    vi.setSystemTime(Date.now() + 50_000)
    document.dispatchEvent(new Event('visibilitychange'))
  })
  expect(screen.getByText('50 s')).toBeInTheDocument()
})

test('the rest ends on time after a locked screen', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Confirm set')
  expect(await screen.findByText('1:00')).toBeInTheDocument()
  act(() => {
    vi.setSystemTime(Date.now() + 61_000)
    document.dispatchEvent(new Event('visibilitychange'))
  })
  expect(await screen.findByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
})

test('confirming with the clock running takes its reading', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const sent = serve({ today: { session: HANG, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Start clock')
  act(() => vi.advanceTimersByTime(37_000))
  click('Confirm set')
  await screen.findByRole('heading', { name: 'Check and save' })
  expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({
    sets: [{ item: 0, set_no: 1, left: 37, right: null }],
  })
})

test('a double tap saves an earlier day once', async () => {
  const sent = serve({ pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }] })
  render(<SessionPage />)
  const button = await screen.findByRole('button', { name: 'Save it' })
  fireEvent.click(button)
  fireEvent.click(button)
  expect(await screen.findByText(/Saved Torso \+ neck/)).toBeInTheDocument()
  expect(sent['POST /api/session/save']).toHaveLength(1)
  expect(screen.queryByRole('button', { name: 'Save it' })).not.toBeInTheDocument()
})

test('a baseline exercise says so on the overview and its set', async () => {
  serve()
  render(<SessionPage />)
  expect(await screen.findByText(/Bodyweight · baseline/)).toBeInTheDocument()
  expect(screen.queryByText(/On a step · baseline/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Start session' }))
  expect(screen.getByText(/Baseline: first time at this step/)).toBeInTheDocument()
})
