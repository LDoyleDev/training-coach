import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Clash, Done, Guided, Kept, Pending, Saved, TodayView } from '../api'
import { playChange, playSessionEnd, unlockAudio } from '../hiit/sounds'
import SessionPage from './SessionPage'

vi.mock('../hiit/sounds', () => ({
  DEFAULT_SOUND: 'ring',
  unlockAudio: vi.fn(),
  playChange: vi.fn(),
  playSessionEnd: vi.fn(),
}))

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
  after_run: false,
  place: 'home',
  place_choice: false,
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
      no_kit: false,
      muscles: [],
      parts: [],
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
      no_kit: false,
      muscles: [],
      parts: [],
    },
  ],
  order: [
    { item: 0, set_no: 1, target: 6, rest_seconds: 15, switch: true },
    { item: 1, set_no: 1, target: 15, rest_seconds: 60, switch: false },
    { item: 0, set_no: 2, target: 6, rest_seconds: 0, switch: false },
  ],
}

const SAVED: Saved = {
  workout_id: 9,
  already_saved: false,
  next_session: 'Recovery + posture',
  earned: [
    {
      exercise: 'Jump squat',
      slug: 'jump-squat',
      unit: 'reps',
      best_set: 7,
      total: 13,
      next_step: null,
      at_top: false,
      unlock: null,
      capped: false,
      load_kg: 22.5,
    },
  ],
  stretching: true,
}

type Server = {
  today?: TodayView | null | 'error'
  keep?: number | 'stale' | 'signed-out'
  save?: Saved | 'stale'
  pending?: Pending[]
  saveEarlier?: 'fail'
  clash?: Clash // answered to a save until it carries a resolution (ADR-0060)
  problem?: string // a 422: why the save was refused
  sound?: string // the timer sound chosen in Settings; unset answers 404
  seen?: boolean | 'error' // the stop signs were read (spec B7); unset means read; 'error' fails the fetch
  place?: TodayView // what a Home | Gym switch answers (ADR-0071)
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
      if (keep === 'signed-out') return new Response(null, { status: 401 })
      return keep === 'stale'
        ? new Response(null, { status: 409 })
        : Response.json({ revision: keep })
    }
    if (path === '/api/session/pending') return Response.json(server.pending ?? [])
    if (path === '/api/session/place' && server.place) return Response.json(server.place)
    if (path === '/api/settings')
      return server.seen === 'error'
        ? new Response(null, { status: 500 })
        : Response.json({ sound: server.sound ?? 'ring', stop_signs_seen: server.seen ?? true })
    if (path === '/api/session/save') {
      if (server.problem) return Response.json({ detail: server.problem }, { status: 422 })
      if (server.clash && !String(init?.body).includes('resolution'))
        return Response.json({ detail: server.clash }, { status: 409 })
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
  vi.clearAllMocks()
  Reflect.deleteProperty(navigator, 'wakeLock')
  localStorage.clear() // a taken weight is kept per browser (ADR-0072)
})

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

/**
 * Moves the fake clock 250 ms at a time, each tick in its own act that lets React finish its
 * work, as a browser would between ticks. A rest's ticker starts in an effect once the save
 * answers, and on a slow run that effect can still be waiting when the rest screen shows: time
 * moved before it runs goes unseen (no counts, only the end). Use after
 * `vi.setTimerTickMode('manual')`, so only these ticks move the clock.
 */
async function tick(ms: number) {
  for (let t = 0; t < ms; t += 250) await act(async () => vi.advanceTimersByTime(250))
}

test('a whole session: overview, sets in pair order, check, save', async () => {
  const sent = serve()
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.getByText('Warm up for about 5 minutes first.')).toBeInTheDocument()
  expect(screen.getByText(/Stop if you feel sharp pain/)).toBeInTheDocument()
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
  expect(playSessionEnd).not.toHaveBeenCalled()
  click('Save session')
  expect(await screen.findByRole('heading', { name: 'Legs done' })).toBeInTheDocument()
  expect(playSessionEnd).toHaveBeenCalledExactlyOnceWith('ring') // saved: the end of the session
  expect(screen.getByText('Next up: Recovery + posture.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '20 min' })).toBeInTheDocument() // stretching
  expect(screen.getByText(/new best 7 in one set at 22\.5 kg/)).toBeInTheDocument()

  const kept = sent['PUT /api/session/progress']
  expect(kept).toHaveLength(3)
  expect(kept[0]).toMatchObject({
    template_id: 3,
    place: 'home',
    revision: 0,
    position: 1,
    sets: [{ item: 0, set_no: 1, left: 7, right: null }],
  })
  expect(kept[2]).toMatchObject({ revision: 1, position: 3 })
})

test('the stop signs show once before the first session, remembered on the server', async () => {
  const sent = serve({ seen: false })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('heading', { name: 'Before you start: stop signs' })).toBeVisible()
  expect(screen.getByText(/Call 112 if it doesn't settle/)).toBeInTheDocument()
  expect(screen.getByText('Sharp joint pain:')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Jump squat' })).not.toBeInTheDocument()
  click('Got it, start')
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  expect(sent['PATCH /api/settings']).toEqual([{ stop_signs_seen: true }])
  click('Leave')
  click(/^(Start|Resume)/)
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument() // not again
})

test('the stop signs still show when the settings fail to load', async () => {
  serve({ seen: 'error' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('heading', { name: 'Before you start: stop signs' })).toBeVisible()
})

test('the stop signs show when Start is tapped before the settings arrive', async () => {
  serve({ seen: true })
  let release = () => {}
  const fetchMock = vi.mocked(fetch)
  const real = fetchMock.getMockImplementation()
  fetchMock.mockImplementation(async (path, init) => {
    if (path === '/api/settings') await new Promise<void>((done) => (release = done))
    return real!(path, init)
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('heading', { name: 'Before you start: stop signs' })).toBeVisible()
  release()
})

test('once read, Start goes straight to the first set', async () => {
  const sent = serve({ seen: true })
  render(<SessionPage />)
  await waitFor(() => expect(sent['GET /api/settings']).toHaveLength(1))
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  expect(sent['PATCH /api/settings']).toBeUndefined()
})

test('the stop signs are one tap away on every set and rest', async () => {
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const signs = screen.getByText('Very dark urine after a hard session:')
  expect(signs).not.toBeVisible()
  fireEvent.click(screen.getByText('Stop signs'))
  expect(signs).toBeVisible()
  click('Confirm set')
  await screen.findByRole('button', { name: 'Skip rest' })
  expect(screen.getByText('Stop signs')).toBeInTheDocument()
})

test('the breathing cue shows once, on the first set after Start (ADR-0084)', async () => {
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const cue = "Breathe out as you push; don't hold your breath."
  expect(screen.getByText(cue)).toBeInTheDocument()
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  await screen.findByRole('heading', { name: 'Calf raise' })
  expect(screen.queryByText(cue)).not.toBeInTheDocument()
})

test('inside a pair the rest is a 15 s switch; after the pair it is a rest (ADR-0065)', async () => {
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Confirm set')
  expect(
    await screen.findByRole('heading', { name: 'Switch to Calf raise · 15 s' }),
  ).toBeInTheDocument()
  expect(screen.getByText('0:15')).toBeInTheDocument()
  click('Skip rest')
  await screen.findByRole('heading', { name: 'Calf raise' })
  click('Confirm set')
  expect(await screen.findByRole('heading', { name: 'Rest · 60 s' })).toBeInTheDocument()
  expect(screen.getByText('1:00')).toBeInTheDocument()
})

test("the set screen shows the step's cue, and the figure set up for that step", async () => {
  const dip = {
    ...SESSION.items[0],
    slug: 'dip',
    name: 'Dip',
    step: 'Dip bars, bodyweight, full range',
    cue: 'Lean slightly forward; elbows back.',
  }
  serve({ today: { session: { ...SESSION, items: [dip, SESSION.items[1]] }, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByText('Lean slightly forward; elbows back.')).toBeInTheDocument()
  expect(
    screen.getByRole('img', { name: /^Dip, moving from: Arms straight on the bars/ }),
  ).toBeVisible()
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
  expect(playSessionEnd).not.toHaveBeenCalled() // not saved: no bell
  click('Back')
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  expect(screen.queryByText(/Today's session changed/)).not.toBeInTheDocument()
})

test.each([
  [null, /Sign in to start today's session/],
  [{ session: null, progress: null }, /Nothing left today/],
  [{ session: { ...SESSION, order: [] }, progress: null }, /Nothing left today/],
  ['error' as const, /Couldn't load today's session/],
])('states without a session: %s', async (today, text) => {
  serve({ today })
  render(<SessionPage />)
  expect(await screen.findByText(text)).toBeInTheDocument()
})

test('with nothing left today, it points to what is next instead of a dead end', async () => {
  serve({ today: { session: null, progress: null } })
  render(<SessionPage />)
  expect(await screen.findByRole('link', { name: 'See my progress' })).toHaveAttribute(
    'href',
    '/progress',
  )
  expect(screen.getByRole('link', { name: 'The week ahead' })).toHaveAttribute(
    'href',
    '/progress?tab=plan',
  )
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
  expect(await screen.findByText('0:15')).toBeInTheDocument() // the switch inside the pair
  expect(screen.getByText('Calf raise')).toBeInTheDocument() // next
  click('+ 15 s')
  expect(screen.getByText('0:30')).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(30_000))
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
    order: [{ item: 0, set_no: 1, target: 30, rest_seconds: 0, switch: false }],
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

const CLASH: Clash = {
  day: '2026-10-11',
  moving: false,
  recorded: [{ workout_id: 4, name: 'Rest day', summary: 'rested' }],
}

test("an earlier day that got its session since asks before it's saved", async () => {
  const sent = serve({
    pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }],
    clash: CLASH,
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save it' }))
  expect(await screen.findByRole('alertdialog')).toHaveTextContent('Rest day: rested')
  click('Add to that day')
  expect(await screen.findByText('Saved Torso + neck for 2026-10-11.')).toBeInTheDocument()
  expect(sent['POST /api/session/save']?.[1]).toEqual({
    day: '2026-10-11',
    resolution: 'add',
    seen: [4],
  })
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

test('cancelling the question saves nothing and keeps the day offered', async () => {
  serve({ pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }], clash: CLASH })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save it' }))
  click(await screen.findByRole('button', { name: 'Cancel' }).then(() => 'Cancel'))
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save it' })).toBeInTheDocument()
})

test("today's session on a day that has one asks at Check and save", async () => {
  const progress: Kept = {
    template_id: 3,
    position: 3,
    first: [],
    sets: [{ item: 0, set_no: 1, left: 6, right: null }],
    saved: false,
    revision: 3,
  }
  const sent = serve({
    today: { session: SESSION, progress },
    clash: { ...CLASH, day: '2026-10-12' },
  })
  render(<SessionPage />)
  click(await screen.findByText('Start session').then(() => 'Start session'))
  click('Save session')
  expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
  click('Replace it')
  expect(await screen.findByRole('heading', { name: 'Legs done' })).toBeInTheDocument()
  expect(sent['POST /api/session/save']?.[1]).toEqual({ resolution: 'replace', seen: [4] })
})

test('a refused save of an earlier day says why and keeps it offered', async () => {
  // Review of #241: a 422 read as "that day changed" and dropped the day.
  serve({
    pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }],
    problem: 'Sun 11 Oct is more than 14 days ago',
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save it' }))
  expect(
    await screen.findByText("Torso + neck wasn't saved: Sun 11 Oct is more than 14 days ago."),
  ).toBeInTheDocument()
  expect(screen.queryByText(/that day changed/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save it' })).toBeInTheDocument()
})

test("a refused save of today's session says why, not that today changed", async () => {
  const progress: Kept = {
    template_id: 3,
    position: 3,
    first: [],
    sets: [{ item: 0, set_no: 1, left: 6, right: null }],
    saved: false,
    revision: 3,
  }
  serve({ today: { session: SESSION, progress }, problem: 'no sets recorded' })
  render(<SessionPage />)
  click(await screen.findByText('Start session').then(() => 'Start session'))
  click('Save session')
  expect(await screen.findByText('Not saved: no sets recorded.')).toBeInTheDocument()
  expect(screen.queryByText(/Today's session changed/)).not.toBeInTheDocument()
})

test('an earlier day that changed since is settled and says so', async () => {
  serve({ pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }], save: 'stale' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save it' }))
  expect(
    await screen.findByText("Torso + neck couldn't be saved: that day changed."),
  ).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Save it' })).not.toBeInTheDocument()
})

test('a failed save of an earlier day keeps it offered', async () => {
  serve({ pending: [{ day: '2026-10-11', session: 'Torso + neck', sets: 5 }], saveEarlier: 'fail' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save it' }))
  expect(await screen.findByText(/Couldn't save. Check your connection/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save it' })).toBeInTheDocument()
})

test('leaving stops a running clock', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const hang: Guided = {
    ...SESSION,
    items: [{ ...SESSION.items[0], name: 'Dead hang', unit: 'seconds', pair: null, targets: [30] }],
    order: [{ item: 0, set_no: 1, target: 30, rest_seconds: 0, switch: false }],
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
  order: [{ item: 0, set_no: 1, target: 30, rest_seconds: 0, switch: false }],
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
  expect(await screen.findByText('0:15')).toBeInTheDocument()
  vi.setTimerTickMode('manual') // from here only the ticks move the clock
  await tick(1_000)
  expect(screen.getByText('0:14')).toBeInTheDocument() // the rest's ticker is running
  act(() => {
    vi.setSystemTime(Date.now() + 16_000)
    document.dispatchEvent(new Event('visibilitychange'))
  })
  // At once: unlocking ends the rest, not the next tick.
  expect(screen.getByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
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

const DUE = { day: 2, name: 'Retest, day 2', tests: ['Bulgarian split squat', '12-minute run'] }

test('a test day due today comes first, and the session waits below it', async () => {
  serve({ today: { session: SESSION, progress: null, test_day: DUE } })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Today: Retest, day 2' })).toBeInTheDocument()
  expect(screen.getByText('Bulgarian split squat, 12-minute run.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Go to the tests' })).toHaveAttribute('href', '/tests')
  expect(screen.getByRole('button', { name: 'Start session' })).toBeInTheDocument()
})

test('a test day shows even with nothing left to train', async () => {
  serve({ today: { session: null, progress: null, test_day: DUE } })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Today: Retest, day 2' })).toBeInTheDocument()
  expect(screen.getByText(/Nothing left today/)).toBeInTheDocument()
})

test('a hard day shows the readiness advice, linking to the questions', async () => {
  const advice = 'Your readiness answers say to check with a doctor before hard efforts.'
  serve({ today: { session: SESSION, progress: null, readiness_note: advice } })
  render(<SessionPage />)
  expect(await screen.findByText(advice)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Readiness questions' })).toHaveAttribute(
    'href',
    '/readiness',
  )
})

test('the readiness advice shows even with nothing left to train', async () => {
  serve({
    today: { session: null, progress: null, test_day: DUE, readiness_note: 'Answer first.' },
  })
  render(<SessionPage />)
  expect(await screen.findByText('Answer first.')).toBeInTheDocument()
})

test('an easy day shows no readiness advice', async () => {
  serve({ today: { session: SESSION, progress: null, readiness_note: null } })
  render(<SessionPage />)
  await screen.findByRole('button', { name: 'Start session' })
  expect(screen.queryByRole('link', { name: 'Readiness questions' })).not.toBeInTheDocument()
})

test("today's daily check shows as a line, with or without a session left", async () => {
  const line = 'Slept OK, a bit sore, high energy: go lighter today'
  serve({ today: { session: SESSION, progress: null, daily_check: line } })
  const { unmount } = render(<SessionPage />)
  expect(await screen.findByText(`Today's check: ${line}.`)).toBeInTheDocument()
  unmount()
  serve({ today: { session: null, progress: null, daily_check: line } })
  render(<SessionPage />)
  expect(await screen.findByText(`Today's check: ${line}.`)).toBeInTheDocument()
})

test('an ended sign-in while confirming a set points to sign in and keeps the set', async () => {
  serve({ keep: 'signed-out' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Confirm set')
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toHaveAttribute(
    'href',
    expect.stringMatching(/^\/signin\?next=/),
  )
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument() // still here
  expect(screen.queryByText(/Check your connection/)).not.toBeInTheDocument()
})

test('confirming again after signing in clears the notice', async () => {
  serve({ keep: 'signed-out' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Confirm set')
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
  vi.unstubAllGlobals()
  serve()
  click('Confirm set')
  expect(await screen.findByRole('button', { name: 'Skip rest' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Sign in again' })).not.toBeInTheDocument()
})

test('a cardio day is logged in one step, not started set by set', async () => {
  const zone2: Guided = {
    ...SESSION,
    name: 'Long zone 2',
    kind: 'conditioning',
    warm_up: false,
    items: [{ ...SESSION.items[0], slug: 'zone2', name: 'Zone 2', unit: 'minutes', pair: null }],
    order: [{ item: 0, set_no: 1, target: 45, rest_seconds: 0, switch: false }],
  }
  serve({ today: { session: zone2, progress: null } })
  render(<SessionPage />)
  // The cardio options failed to load here, so the card offers both ways in.
  expect(await screen.findByRole('heading', { name: 'Cardio or HIIT' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Start session' })).not.toBeInTheDocument()
})

const CARDIO_CORE: Guided = {
  ...SESSION,
  name: 'Cardio + core',
  kind: 'conditioning',
  warm_up: false,
  items: [
    {
      ...SESSION.items[0],
      slug: 'moderate-cardio',
      name: 'Moderate cardio',
      unit: 'minutes',
      pair: null,
    },
    { ...SESSION.items[0], slug: 'ab-rollout', name: 'Ab rollout', pair: 1 },
    { ...SESSION.items[1], slug: 'copenhagen-plank', name: 'Copenhagen plank', pair: 1 },
  ],
  order: [{ item: 0, set_no: 1, target: 35, rest_seconds: 0, switch: false }],
}

test('a cardio day with a block after the run logs the run first (ADR-0066)', async () => {
  serve({ today: { session: CARDIO_CORE, progress: null } })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Cardio or HIIT' })).toBeInTheDocument()
  expect(
    screen.getByText('After your run: Ab rollout, Copenhagen plank. Log the run, then this opens.'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Start session' })).not.toBeInTheDocument()
})

test('once the run is logged, the rest of the session is guided after it', async () => {
  const after: Guided = {
    ...CARDIO_CORE,
    after_run: true,
    items: CARDIO_CORE.items.slice(1),
    order: [
      { item: 0, set_no: 1, target: 8, rest_seconds: 15, switch: true },
      { item: 1, set_no: 1, target: 6, rest_seconds: 0, switch: false },
    ],
  }
  serve({ today: { session: after, progress: null } })
  render(<SessionPage />)
  expect(await screen.findByRole('button', { name: 'Start session' })).toBeInTheDocument()
  expect(
    screen.getByText("After your run: it's logged, and these sets are saved with it."),
  ).toBeInTheDocument()
  expect(screen.queryByText(/Log the run, then this opens/)).not.toBeInTheDocument()
})

test('cardio and HIIT stay on offer under any session, and once the day is done', async () => {
  serve()
  const { unmount } = render(<SessionPage />)
  expect(await screen.findByRole('button', { name: 'Start session' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run a HIIT session' })).toBeInTheDocument()
  unmount()
  serve({ today: { session: null } })
  render(<SessionPage />)
  expect(await screen.findByText('Nothing left today')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Log cardio' })).toBeInTheDocument()
})

test('each set is sent with when its screen appeared and when it was confirmed', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.setSystemTime(new Date('2026-10-20T16:00:00Z'))
  const sent = serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const shown = Date.now()
  act(() => vi.advanceTimersByTime(40_000))
  click('Confirm set')
  await screen.findByText('0:15')
  act(() => vi.advanceTimersByTime(15_000)) // the switch runs out: the next set shows
  expect(await screen.findByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(30_000))
  click('Confirm set')
  await screen.findByText('1:00')
  const [first, second] = (sent['PUT /api/session/progress'] ?? []) as { sets: Done[] }[]
  const [jump] = first.sets
  expect(Date.parse(jump.started_at ?? '')).toBeGreaterThanOrEqual(shown - 1000)
  expect(Date.parse(jump.started_at ?? '')).toBeLessThanOrEqual(shown)
  expect(Date.parse(jump.done_at ?? '') - Date.parse(jump.started_at ?? '')).toBeGreaterThanOrEqual(
    40_000,
  )
  expect(second.sets[0]).toEqual(jump) // the first set's times don't change
  // The next set is timed from the switch's end: 15 s after the confirm.
  const rest = Date.parse(second.sets[1].started_at ?? '') - Date.parse(jump.done_at ?? '')
  expect(rest).toBeGreaterThanOrEqual(15_000)
  expect(rest).toBeLessThan(16_000)
})

test('a set fixed with Back keeps the times of its first confirm', async () => {
  const at = { started_at: '2026-10-20T16:00:00.000Z', done_at: '2026-10-20T16:00:40.000Z' }
  const progress: Kept = {
    template_id: 3,
    position: 1,
    first: [],
    sets: [{ item: 0, set_no: 1, left: 6, right: null, ...at }],
    saved: false,
    revision: 2,
  }
  const sent = serve({ today: { session: SESSION, progress } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume: set 2 of 3' }))
  click('Back')
  click('1 fewer')
  click('Confirm set')
  await screen.findByText('0:15') // back to the calf raise: the switch that leads into it
  expect(sent['PUT /api/session/progress']?.[0]).toMatchObject({
    sets: [{ item: 0, set_no: 1, left: 5, right: null, ...at }],
  })
})

test('the overview says how long this session usually takes, once it has been timed', async () => {
  serve({ today: { session: { ...SESSION, usual_minutes: 38 }, progress: null } })
  render(<SessionPage />)
  expect(await screen.findByText('Usually 38 min')).toBeInTheDocument()
})

test("before any timed session, the overview gives the plan's estimate", async () => {
  serve()
  render(<SessionPage />)
  expect(await screen.findByText('About 45 min')).toBeInTheDocument()
})

test.each([
  [0, 'Took 41 min: 22 on sets, 19 resting.'],
  [1, 'Took 41 min: 22 on sets, 19 resting, plus 1 break.'],
  [2, 'Took 41 min: 22 on sets, 19 resting, plus 2 breaks.'],
])('the saved screen says how long it took (%i breaks)', async (breaks, text) => {
  const progress: Kept = {
    template_id: 3,
    position: 3,
    first: [],
    sets: [],
    saved: false,
    revision: 1,
  }
  serve({
    today: { session: SESSION, progress },
    save: { ...SAVED, timing: { minutes: 41, on_sets: 22, resting: 19, breaks } },
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Save session')
  expect(await screen.findByText(text)).toBeInTheDocument()
})

test('an untimed save says nothing about time', async () => {
  const progress: Kept = {
    template_id: 3,
    position: 3,
    first: [],
    sets: [],
    saved: false,
    revision: 1,
  }
  serve({ today: { session: SESSION, progress } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Save session')
  expect(await screen.findByRole('heading', { name: 'Legs done' })).toBeInTheDocument()
  expect(screen.queryByText(/^Took /)).not.toBeInTheDocument()
})

test.each([
  [
    'an 8 kg kettlebell unlocks Holding 8 kg',
    true,
    /top of the range on the last level your kit allows\. An 8 kg kettlebell unlocks Holding 8 kg\./,
  ],
  [null, false, /top of the range on the last level of its ladder\./],
  // Harder steps above, every one locked otherwise: true, and never why (ADR-0083).
  [null, true, /top of the range, with no open step above this one\./],
])(
  'the rule met with no level to move to says so (unlock %s, capped %s)',
  async (unlock, capped, text) => {
    const progress: Kept = {
      template_id: 3,
      position: 3,
      first: [],
      sets: [],
      saved: false,
      revision: 1,
    }
    const earned = { ...SAVED.earned[0], best_set: null, total: null, at_top: true, unlock, capped }
    serve({ today: { session: SESSION, progress }, save: { ...SAVED, earned: [earned] } })
    render(<SessionPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
    click('Save session')
    expect(await screen.findByText(text)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /ready to move up/ })).not.toBeInTheDocument()
    const kit = screen.queryByRole('link', { name: 'My equipment' })
    expect(kit === null).toBe(unlock === null)
    if (kit) expect(kit).toHaveAttribute('href', '/account#my-equipment')
  },
)

test('the mobility item plays its flow and logs the minutes moved as its set', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.setSystemTime(new Date('2026-10-20T16:00:00Z'))
  const move = {
    slug: 'cat-cow',
    name: 'Cat-cow',
    seconds: 60,
    per_side: false,
    target: 'The whole spine',
    start: 'All fours, back rounded.',
    end: 'All fours, back arched.',
    cues: ['Move slowly.'],
    breathing: 'Out as you round.',
    easier: 'Move less far.',
    pacing: 'Slow reps.',
  }
  const recovery: Guided = {
    ...SESSION,
    name: 'Recovery + posture',
    kind: 'recovery',
    warm_up: false,
    items: [
      {
        slug: 'mobility',
        name: 'Mobility flow',
        step: 'Guided 10 min',
        summary: 'Eight slow movements.',
        cue: null,
        unit: 'minutes',
        per_side: false,
        pair: null,
        targets: [10],
        baseline: false,
        no_kit: false,
        muscles: [],
        parts: [],
        flow: { seconds: 120, safety: 'If something hurts, stop.', moves: [move, move] },
      },
    ],
    order: [{ item: 0, set_no: 1, target: 10, rest_seconds: 0, switch: false }],
  }
  const sent = serve({ today: { session: recovery, progress: null }, sound: 'chime' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.queryByRole('button', { name: 'Confirm set' })).not.toBeInTheDocument()
  const started = Date.now()
  click('Start the flow')
  expect(screen.getByRole('heading', { name: 'Cat-cow' })).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(121_000))
  // The flow is the session's last set: its end is the end of the session, rung once.
  expect(playSessionEnd).toHaveBeenCalledExactlyOnceWith('chime')
  expect(playChange).not.toHaveBeenCalledWith('chime', 'finish')
  click('Log 2 min')
  await screen.findByRole('heading', { name: 'Check and save' })
  const [kept] = (sent['PUT /api/session/progress'] ?? []) as { sets: Done[] }[]
  expect(kept.sets).toHaveLength(1)
  expect(kept.sets[0]).toMatchObject({ item: 0, set_no: 1, left: 2, right: null })
  expect(Date.parse(kept.sets[0].started_at ?? '')).toBe(started)
  click('Save session')
  expect(
    await screen.findByRole('heading', { name: 'Recovery + posture done' }),
  ).toBeInTheDocument()
  expect(playSessionEnd).toHaveBeenCalledOnce() // the save doesn't ring it twice
})

test('the set screen says the muscles an exercise works, beside a picture of them', async () => {
  const pullUp = {
    ...SESSION.items[0],
    muscles: [
      { muscle: 'lats', weight: 1 },
      { muscle: 'upper back', weight: 0.5 },
      { muscle: 'biceps', weight: 0.5 },
      { muscle: 'rear delts', weight: 0.25 },
      { muscle: 'forearms', weight: 0.25 },
    ],
  }
  serve({ today: { session: { ...SESSION, items: [pullUp, SESSION.items[1]] }, progress: null } })
  const { container } = render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByText('Squat, then jump.')).toBeInTheDocument()
  expect(
    screen.getByText('Works: Lats · helped by upper back, biceps · a little: rear delts, forearms'),
  ).toBeInTheDocument()
  expect(container.querySelector('path[data-muscle="lats"]')).toHaveAttribute(
    'fill',
    'var(--heat-hard)',
  )
  // The words carry the meaning; the figures are hidden from assistive tech.
  expect(screen.queryAllByRole('figure')).toHaveLength(0)
  expect(screen.getAllByRole('figure', { hidden: true })).toHaveLength(2)
  expect(screen.getByRole('button', { name: 'Confirm set' })).toBeInTheDocument()
})

test('an exercise that works no muscle has no muscles line or figures', async () => {
  serve()
  const { container } = render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByText('Squat, then jump.')).toBeInTheDocument()
  expect(screen.queryByText(/^Works:/)).not.toBeInTheDocument()
  expect(container.querySelector('path[data-muscle]')).toBeNull()
})

test('a drawn exercise always shows its movement, with no toggle', async () => {
  const pushUp = { ...SESSION.items[0], slug: 'push-up', name: 'Push-up' }
  const undrawn = { ...SESSION.items[1], slug: 'not-drawn-yet' }
  serve({ today: { session: { ...SESSION, items: [pushUp, undrawn] }, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('img', { name: /^Push-up, moving from:/ })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /the movement/ })).not.toBeInTheDocument()

  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  expect(await screen.findByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
  expect(screen.queryByRole('img', { name: /moving from/ })).not.toBeInTheDocument() // undrawn
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))

  expect(await screen.findByText('Set 2 of 2')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /^Push-up, moving from:/ })).toBeInTheDocument()
})

const follows = (before: Element, after: Element) =>
  Boolean(before.compareDocumentPosition(after) & Node.DOCUMENT_POSITION_FOLLOWING)

test('the set screen puts the counter first, then the how-to, the movement, the muscles', async () => {
  const pushUp = {
    ...SESSION.items[0],
    slug: 'push-up',
    name: 'Push-up',
    summary: 'Lower your chest to the floor.',
    muscles: [{ muscle: 'chest', weight: 1 }],
  }
  serve({ today: { session: { ...SESSION, items: [pushUp, SESSION.items[1]] }, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const inOrder = [
    screen.getByRole('heading', { name: 'Push-up' }),
    screen.getByRole('button', { name: 'Do Calf raise first' }),
    screen.getByText('Set 1 of 2'),
    screen.getByRole('group', { name: 'Reps' }),
    screen.getByRole('button', { name: 'Confirm set' }),
    screen.getByText('Lower your chest to the floor.'),
    screen.getByRole('img', { name: /^Push-up, moving from:/ }),
    screen.getByText(/^Works: Chest/),
  ]
  inOrder.slice(1).forEach((el, n) => expect(follows(inOrder[n], el)).toBe(true))
})

test('a timed set shows its clock under the set heading, above the confirm', async () => {
  serve({ today: { session: HANG, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const clock = screen.getByRole('button', { name: 'Start clock' })
  expect(follows(screen.getByText('Set 1 of 1', { selector: '.text-lg' }), clock)).toBe(true)
  expect(follows(clock, screen.getByRole('button', { name: 'Confirm set' }))).toBe(true)
})

test("a rest counts its last 3 seconds and ends in the person's timer sound", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const vibrate = vi.fn()
  vi.stubGlobal('navigator', { ...navigator, vibrate })
  serve({ sound: 'wood' })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  await act(async () => {}) // the settings arrive
  expect(unlockAudio).toHaveBeenCalled() // inside the Start tap
  expect(playChange).not.toHaveBeenCalled() // nothing plays on Start
  click('Confirm set')
  await screen.findByText('0:15')
  vi.setTimerTickMode('manual') // from here only the ticks move the clock
  await tick(11_000)
  expect(playChange).not.toHaveBeenCalled()
  await tick(4_500)
  expect(screen.getByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
  expect(vi.mocked(playChange).mock.calls).toEqual([
    ['wood', 'count'],
    ['wood', 'count'],
    ['wood', 'count'],
    ['wood', 'next'],
  ])
  expect(vibrate).toHaveBeenCalledWith(300)
})

test('a skipped rest plays nothing', async () => {
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  expect(await screen.findByRole('heading', { name: 'Calf raise' })).toBeInTheDocument()
  expect(playChange).not.toHaveBeenCalled()
})

test('the screen stays on through sets and rests, and is let go on leaving', async () => {
  const release = vi.fn(async () => {})
  const request = vi.fn(async () => ({ release }))
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(request).toHaveBeenCalledWith('screen')
  await act(async () => {})
  click('Confirm set')
  await screen.findByText('0:15')
  expect(release).not.toHaveBeenCalled() // still on through the rest
  click('Skip rest')
  await screen.findByRole('heading', { name: 'Calf raise' })
  click('Leave')
  await act(async () => {})
  expect(release).toHaveBeenCalled()
})

test('without a wake lock the session still runs', async () => {
  Object.defineProperty(navigator, 'wakeLock', {
    value: {
      request: () => {
        throw new Error('not allowed')
      },
    },
    configurable: true,
  })
  serve()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('button', { name: 'Confirm set' })).toBeInTheDocument()
})

test('Check and save shows the time so far and each set time, marking time lost', async () => {
  const at = (from: string, to: string) => ({
    started_at: `2026-10-20T16:${from}.000Z`,
    done_at: `2026-10-20T16:${to}.000Z`,
  })
  const progress: Kept = {
    template_id: 3,
    position: 3,
    first: [],
    sets: [
      { item: 0, set_no: 1, left: 6, right: null, ...at('00:00', '00:34') },
      { item: 1, set_no: 1, left: 15, right: null, ...at('00:49', '01:20') }, // a 15 s switch
      // 100 s since the calf raise against a planned 60, and much slower than the first set.
      { item: 0, set_no: 2, left: 6, right: null, ...at('03:00', '04:00') },
    ],
    saved: false,
    revision: 1,
  }
  serve({ today: { session: SESSION, progress } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(await screen.findByRole('heading', { name: 'Check and save' })).toBeInTheDocument()
  expect(screen.getByText('So far 4 min: 2 on sets, 2 resting.')).toBeInTheDocument()
  expect(screen.getByText('34s')).not.toHaveClass('font-bold')
  const slow = screen.getByText('60s', { exact: false, selector: 'span.font-bold' })
  expect(slow).toHaveTextContent('60s (slow)') // said, not only shown
  expect(screen.getByText(/\+40s rest/)).toBeInTheDocument()
  expect(screen.getByText('31s')).toBeInTheDocument()
})

test('Check and save shows no times for sets without them', async () => {
  const progress: Kept = {
    template_id: 3,
    position: 3,
    first: [],
    sets: [{ item: 0, set_no: 1, left: 6, right: null }],
    saved: false,
    revision: 1,
  }
  serve({ today: { session: SESSION, progress } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(await screen.findByRole('heading', { name: 'Check and save' })).toBeInTheDocument()
  expect(screen.queryByText(/^So far/)).not.toBeInTheDocument()
  expect(screen.queryByText(/^\d+s$/)).not.toBeInTheDocument()
})

const LOADED: Guided = {
  ...SESSION,
  items: [
    {
      ...SESSION.items[0],
      name: 'Bench press',
      load: { kit: 'barbell', increment: 2.5, kg: [40, 42.5], carried: true },
    },
    SESSION.items[1],
  ],
}

test('a loaded step starts at last time and takes − and + in its increment (ADR-0072)', async () => {
  const sent = serve({ today: { session: LOADED, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const weight = screen.getByRole('group', { name: 'Weight, kg' })
  expect(weight).toHaveTextContent('40')
  expect(weight).toHaveTextContent('Same as last time')
  click('2.5 kg heavier')
  expect(weight).toHaveTextContent('42.5')
  expect(weight).toHaveTextContent('Last time 40 kg')
  expect(screen.queryByRole('group', { name: 'Each dumbbell, kg' })).not.toBeInTheDocument()
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  await screen.findByRole('heading', { name: 'Calf raise' })
  expect(screen.queryByRole('group', { name: 'Weight, kg' })).not.toBeInTheDocument()
  click('Confirm set')
  expect(await screen.findByText(/set 2 of 2, target 6 at 42.5 kg/)).toBeInTheDocument()
  click('Skip rest')
  await screen.findByRole('heading', { name: 'Bench press' })
  click('Confirm set')
  expect(await screen.findByText('6 · 6 at 42.5 kg')).toBeInTheDocument()
  const kept = sent['PUT /api/session/progress']
  expect(kept[0]).toMatchObject({ sets: [{ item: 0, set_no: 1, left: 6, load_kg: 42.5 }] })
  expect((kept[1] as { sets: Done[] }).sets[1]).not.toHaveProperty('load_kg')
})

test('a first time at a loaded step says to set the weight, and the next set follows it', async () => {
  const first: Guided = {
    ...LOADED,
    items: [
      {
        ...LOADED.items[0],
        load: { kit: 'dumbbells', increment: 2, kg: [8, 8], carried: false },
      },
      LOADED.items[1],
    ],
  }
  serve({ today: { session: first, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const weight = screen.getByRole('group', { name: 'Each dumbbell, kg' })
  expect(weight).toHaveTextContent('First time at this step: set your weight')
  click('2 kg lighter')
  click('2 kg lighter')
  click('2 kg lighter')
  expect(screen.getByRole('button', { name: '2 kg lighter' })).toBeDisabled()
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  await screen.findByRole('heading', { name: 'Calf raise' })
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  const next = await screen.findByRole('group', { name: 'Each dumbbell, kg' })
  expect(next).toHaveTextContent('−2+')
})

test('at home − and + step through the weights owned; none heavier names what opens it', async () => {
  const home: Guided = {
    ...LOADED,
    items: [
      {
        ...LOADED.items[0],
        load: {
          kit: 'dumbbells',
          increment: 2,
          kg: [12, 12],
          carried: true,
          owned: [10, 12, 16],
          unlock: '18 kg dumbbells',
        },
      },
      LOADED.items[1],
    ],
  }
  serve({ today: { session: home, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const weight = screen.getByRole('group', { name: 'Each dumbbell, kg' })
  click(/^Heavier: 16\skg$/)
  expect(weight).toHaveTextContent('16')
  expect(screen.getByRole('button', { name: 'Heavier' })).toBeDisabled() // none heavier owned
  click(/^Lighter: 12\skg$/)
  click(/^Lighter: 10\skg$/)
  expect(weight).toHaveTextContent('10')
  expect(screen.getByRole('button', { name: 'Lighter' })).toBeDisabled()
  expect(
    screen.getByText(/Top for your kit: 18 kg dumbbells would open the next weight\./),
  ).toBeInTheDocument()
  expect(screen.queryByRole('group', { name: 'Next weight' })).not.toBeInTheDocument()
})

test('a vest or backpack step counts the weight added, from 5 kg in the persons step', async () => {
  const vest: Guided = {
    ...LOADED,
    items: [
      {
        ...LOADED.items[0],
        load: { kit: 'backpack', increment: 1, kg: [5, 5], carried: false, owned: [5, 6, 7] },
      },
      LOADED.items[1],
    ],
  }
  serve({ today: { session: vest, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const weight = screen.getByRole('group', { name: 'Added weight, kg' })
  expect(weight).toHaveTextContent('5')
  expect(screen.getByRole('button', { name: 'Lighter' })).toBeDisabled()
  click(/^Heavier: 6\skg$/)
  expect(weight).toHaveTextContent('6')
})

test('every set at the top last time offers the next weight; a tap takes it or goes back', async () => {
  const ready: Guided = {
    ...LOADED,
    items: [
      {
        ...LOADED.items[0],
        load: {
          kit: 'barbell',
          increment: 2.5,
          kg: [40, 40],
          carried: true,
          suggested: { kg: 42.5, targets: [4, 4] },
        },
      },
      LOADED.items[1],
    ],
  }
  const sent = serve({ today: { session: ready, progress: null } })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  const next = screen.getByRole('group', { name: 'Next weight' })
  expect(next).toHaveTextContent('Every set reached the top of the range last time.')
  expect(screen.getByRole('group', { name: 'Weight, kg' })).toHaveTextContent('40')
  expect(screen.getByText('Target 6')).toBeInTheDocument() // nothing changes until a tap
  click('1 more') // a set touched before the tap still takes the new weight
  click(/^Use 42\.5\skg$/)
  expect(screen.getByRole('group', { name: 'Weight, kg' })).toHaveTextContent('42.5')
  expect(screen.getByRole('group', { name: 'Weight, kg' })).toHaveTextContent('Last time 40 kg')
  expect(screen.getByText('Target 4')).toBeInTheDocument()
  expect(next).toHaveTextContent('Taking 42.5 kg: reps start again from 4.')
  click(/^Stay at 40\skg$/)
  expect(screen.getByText('Target 6')).toBeInTheDocument()
  click(/^Use 42\.5\skg$/)
  click('Confirm set')
  await waitFor(() => expect(sent['PUT /api/session/progress']).toHaveLength(1))
  expect(sent['PUT /api/session/progress'][0]).toMatchObject({
    sets: [{ item: 0, set_no: 1, left: 4, load_kg: 42.5 }],
  })
})

const READY: Guided = {
  ...LOADED,
  items: [
    {
      ...LOADED.items[0],
      load: {
        kit: 'barbell',
        increment: 2.5,
        kg: [40, 40],
        carried: true,
        suggested: { kg: 42.5, targets: [4, 4] },
      },
    },
    LOADED.items[1],
  ],
}

/** Resumed at the bench press's second set, its first kept at ``kg`` with no set times (kept
 * before ADR-0061, or by another client). */
const resumedAt = (kg: number): TodayView => ({
  session: READY,
  progress: {
    template_id: 3,
    position: 2,
    first: [],
    saved: false,
    revision: 2,
    sets: [
      { item: 0, set_no: 1, left: 6, right: null, load_kg: kg },
      { item: 1, set_no: 1, left: 15, right: null },
    ],
  },
})

test('taking the suggestion on a resumed session keeps sets confirmed without times', async () => {
  const sent = serve({ today: resumedAt(40) })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume: set 3 of 3' }))
  click(/^Use 42\.5\skg$/)
  click('Confirm set')
  await waitFor(() => expect(sent['PUT /api/session/progress']).toHaveLength(1))
  const kept = (sent['PUT /api/session/progress'][0] as { sets: Done[] }).sets
  expect(kept.map((d) => [d.item, d.set_no, d.load_kg ?? null])).toEqual([
    [0, 1, 40],
    [1, 1, null],
    [0, 2, 42.5],
  ])
})

test('reaching the suggested weight with + is not taking it, after a reload too', async () => {
  serve({ today: resumedAt(42.5) })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume: set 3 of 3' }))
  expect(screen.getByRole('group', { name: 'Next weight' })).toHaveTextContent('Ready for')
  expect(screen.getByText('Target 6')).toBeInTheDocument()
})

test('a tap on Use is kept through a reload of the page', async () => {
  serve({ today: resumedAt(42.5) })
  const first = render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume: set 3 of 3' }))
  click(/^Use 42\.5\skg$/)
  first.unmount()
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume: set 3 of 3' }))
  expect(screen.getByRole('group', { name: 'Next weight' })).toHaveTextContent('Taking 42.5')
  expect(screen.getByText('Target 4')).toBeInTheDocument()
})

test('at both places, Home | Gym changes the day and the sets kept name the version', async () => {
  const atBoth: Guided = { ...SESSION, place_choice: true }
  const gym: Guided = { ...atBoth, place: 'gym', name: 'Legs' }
  const sent = serve({
    today: { session: atBoth, progress: null },
    place: { session: gym, progress: null },
  })
  render(<SessionPage />)
  const home = await screen.findByRole('button', { name: 'Home' })
  expect(home).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('The home version, with your own kit.')).toBeInTheDocument()
  click('Gym')
  expect(await screen.findByText('Legs at the gym: its gym version.')).toBeInTheDocument()
  expect(sent['PUT /api/session/place']).toEqual([{ place: 'gym', confirm: false }])
  expect(screen.getByRole('button', { name: 'Gym' })).toHaveAttribute('aria-pressed', 'true')
  click('Start session')
  click('Confirm set')
  await waitFor(() => expect(sent['PUT /api/session/progress']).toHaveLength(1))
  expect(sent['PUT /api/session/progress'][0]).toMatchObject({ place: 'gym' })
})

test('the switch shows only when today has both versions', async () => {
  serve()
  render(<SessionPage />)
  await screen.findByRole('button', { name: 'Start session' })
  expect(screen.queryByText('Where are you training today?')).not.toBeInTheDocument()
})
