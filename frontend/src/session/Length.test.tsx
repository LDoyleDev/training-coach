import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { CardioOptions, Guided, Length, TodayView } from '../api'
import { emptyWeek } from '../test/cardioWeek'
import SessionPage from './SessionPage'

vi.mock('../hiit/sounds', () => ({
  DEFAULT_SOUND: 'ring',
  unlockAudio: vi.fn(),
  playChange: vi.fn(),
  playSessionEnd: vi.fn(),
}))

const item = (slug: string, name: string, pair: number | null, targets: number[]) => ({
  slug,
  name,
  step: 'Bodyweight',
  summary: null,
  cue: null,
  unit: 'reps' as const,
  per_side: false,
  pair,
  targets,
  baseline: false,
  no_kit: false,
  muscles: [],
  parts: [],
  last_set_amrap: false,
})

const PLANNED: Length = {
  minutes: null,
  options: [40, 30, 20],
  keep: [],
  planned_minutes: 49,
  dropped: [],
  warm_up: 'full',
  shortest: null,
  fixed: false,
  from_setting: false,
}

const SESSION: Guided = {
  day: '2026-10-31',
  template_id: 3,
  name: 'Legs',
  focus: 'Quads, hamstrings',
  kind: 'strength',
  warm_up: true,
  block: null,
  minutes: 49,
  usual_minutes: 52,
  rest_seconds: 60,
  after_run: false,
  place: 'home',
  place_choice: false,
  items: [
    item('jump-squat', 'Jump squat', 1, [6, 6]),
    item('calf-raise', 'Calf raise', 1, [15, 15]),
    item('plank', 'Plank', null, [30]),
  ],
  order: [
    { item: 0, set_no: 1, target: 6, rest_seconds: 15, switch: true },
    { item: 1, set_no: 1, target: 15, rest_seconds: 60, switch: false },
    { item: 0, set_no: 2, target: 6, rest_seconds: 15, switch: true },
    { item: 1, set_no: 2, target: 15, rest_seconds: 60, switch: false },
    { item: 2, set_no: 1, target: 30, rest_seconds: 0, switch: false },
  ],
  length: PLANNED,
}

/** The session at 20 min: calf raise and plank dropped, kept in the items with no sets. */
const SHORT: Guided = {
  ...SESSION,
  warm_up: false,
  minutes: 18,
  items: [
    item('jump-squat', 'Jump squat', 1, [6, 6]),
    item('calf-raise', 'Calf raise', 1, []),
    item('plank', 'Plank', null, []),
  ],
  order: [
    { item: 0, set_no: 1, target: 6, rest_seconds: 60, switch: false },
    { item: 0, set_no: 2, target: 6, rest_seconds: 0, switch: false },
  ],
  length: {
    ...PLANNED,
    minutes: 20,
    dropped: ['Plank', 'Calf raise'],
    warm_up: 'ramp',
  },
}

const today = (session: Guided | null, revision = 0): TodayView => ({
  session,
  progress:
    session && revision
      ? { template_id: 3, position: 0, first: [], sets: [], saved: false, revision }
      : null,
})

type Server = {
  today?: TodayView[] | 'error' // each GET takes the next; the last repeats
  length?: Response[] // each PUT /length takes the next
  cardio?: CardioOptions[] // each GET /api/cardio takes the next; the last repeats
}

/** A fake API; returns the bodies sent, by method and path. */
function serve(server: Server) {
  const sent: Record<string, unknown[]> = {}
  const days = server.today === 'error' ? [] : [...(server.today ?? [today(SESSION)])]
  const cardio = [...(server.cardio ?? [])]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      ;(sent[`${method} ${path}`] ??= []).push(init?.body ? JSON.parse(String(init.body)) : null)
      if (path === '/api/session/today') {
        if (server.today === 'error') return new Response(null, { status: 500 })
        return Response.json(days.length > 1 ? days.shift() : days[0])
      }
      if (path === '/api/session/length')
        return server.length?.shift() ?? new Response(null, { status: 500 })
      if (path === '/api/cardio' && cardio.length)
        return Response.json(cardio.length > 1 ? cardio.shift() : cardio[0])
      if (path === '/api/session/progress') return Response.json({ revision: 2 })
      if (path === '/api/session/pending') return Response.json([])
      if (path === '/api/settings') return Response.json({ sound: 'ring', stop_signs_seen: true })
      return new Response(null, { status: 404 })
    }),
  )
  return sent
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const button = (name: string | RegExp) => screen.getByRole('button', { name })
const choice = () => screen.getByRole('group', { name: 'Short on time today?' })

test('loading, then the choice as planned; nothing is recommended', async () => {
  serve({})
  render(<SessionPage />)
  expect(screen.getByText("Loading today's session…")).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  const options = within(choice()).getAllByRole('button')
  expect(options.map((b) => b.textContent)).toEqual(['As planned', '40 min', '30 min', '20 min'])
  expect(button('As planned')).toHaveAttribute('aria-pressed', 'true')
  expect(
    screen.getByText('About 49 min as planned. For today only; the plan stays the same.'),
  ).toBeInTheDocument()
  expect(screen.getByText('Usually 52 min')).toBeInTheDocument()
  expect(screen.getByText('Warm up for about 5 minutes first.')).toBeInTheDocument()
  expect(screen.queryByText(/Dropped today/)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Keep / })).not.toBeInTheDocument()
  expect(screen.queryByText(/recommend/i)).not.toBeInTheDocument()
  fireEvent.click(button('As planned')) // already chosen: nothing is sent
  expect(fetch).not.toHaveBeenCalledWith('/api/session/length', expect.anything())
})

test('choosing a length sends it with the revision and names what is dropped', async () => {
  const sent = serve({ today: [today(SESSION, 4)], length: [Response.json(today(SHORT, 5))] })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: '20 min' }))
  expect(await screen.findByText('Dropped today: Plank, Calf raise.')).toBeInTheDocument()
  expect(sent['PUT /api/session/length']).toEqual([
    { template_id: 3, place: 'home', revision: 4, first: [], minutes: 20, keep: [] },
  ])
  expect(screen.getByText('Legs at 20 min.')).toBeInTheDocument()
  expect(button('20 min')).toHaveAttribute('aria-pressed', 'true')
  expect(
    screen.getByText('About 18 min at this length, warm-up included. As planned: about 49 min.'),
  ).toBeInTheDocument()
  expect(screen.getByText('About 18 min')).toBeInTheDocument() // not "usually": a shorter day
  // Ramp sets in place of the 5-minute warm-up.
  expect(
    screen.getByText(
      'Warm-up: one or two easy sets of the first exercise at about half its target.',
    ),
  ).toBeInTheDocument()
  expect(screen.queryByText('Warm up for about 5 minutes first.')).not.toBeInTheDocument()
  // Dropped exercises stay in the list, said in words; a pair left alone isn't a pair.
  const row = (name: string) => screen.getByText(name, { selector: 'span' }).closest('li')!
  expect(within(row('Calf raise')).getByText('Dropped today')).toBeInTheDocument()
  expect(within(row('Jump squat')).queryByText(/Pair 1/)).not.toBeInTheDocument()
})

test('Keep pins an exercise at the chosen length, and a second tap lets it go', async () => {
  const kept = { ...SESSION, length: { ...PLANNED, minutes: 20, keep: ['plank'] } }
  const sent = serve({
    today: [today(SHORT, 5)],
    length: [Response.json(today(kept, 6)), Response.json(today(SHORT, 7))],
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Keep Plank' }))
  expect(await screen.findByText('Plank stays in today.')).toBeInTheDocument()
  expect(button('Keep Plank')).toHaveAttribute('aria-pressed', 'true')
  expect(button('Keep Plank')).toHaveTextContent('✓ Keep')
  fireEvent.click(button('Keep Plank'))
  expect(await screen.findByText('Plank can be dropped again.')).toBeInTheDocument()
  expect(sent['PUT /api/session/length']).toEqual([
    { template_id: 3, place: 'home', revision: 5, first: [], minutes: 20, keep: ['plank'] },
    { template_id: 3, place: 'home', revision: 6, first: [], minutes: 20, keep: [] },
  ])
})

test('a 409 reloads the session and says why', async () => {
  const started = { ...SHORT, length: { ...SHORT.length!, fixed: true } }
  const sent = serve({
    today: [today(SESSION, 1), today(started, 3)],
    length: [Response.json({ detail: 'this session has started' }, { status: 409 })],
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: '30 min' }))
  expect(
    await screen.findByText(
      "Today's session moved on elsewhere, so its length wasn't changed. Here it is now.",
    ),
  ).toBeInTheDocument()
  expect(
    await screen.findByText('20 min today, about 18 min. It stays like this now a set is kept.'),
  ).toBeInTheDocument()
  expect(sent['GET /api/session/today']).toHaveLength(2)
})

test('once a set is kept the length is words, not buttons, and Keep is gone', async () => {
  serve({ today: [today({ ...SHORT, length: { ...SHORT.length!, fixed: true } }, 3)] })
  render(<SessionPage />)
  expect(
    await screen.findByText('20 min today, about 18 min. It stays like this now a set is kept.'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('group', { name: 'Short on time today?' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Keep / })).not.toBeInTheDocument()
  expect(screen.getByText('Dropped today: Plank, Calf raise.')).toBeInTheDocument()
})

test('fixed as planned says so', async () => {
  serve({ today: [today({ ...SESSION, length: { ...PLANNED, fixed: true } }, 3)] })
  render(<SessionPage />)
  expect(
    await screen.findByText(
      'As planned today, about 49 min. It stays like this now a set is kept.',
    ),
  ).toBeInTheDocument()
})

test('when the minutes cannot be met it says the shortest and shows that version', async () => {
  const floor = { ...SHORT, minutes: 24, length: { ...SHORT.length!, shortest: 24 } }
  serve({ today: [today(floor, 2)] })
  render(<SessionPage />)
  expect(
    await screen.findByText(
      'The shortest this session gets is 24 minutes. The session below is that version.',
    ),
  ).toBeInTheDocument()
})

test('the guided session skips dropped exercises and checks only what was done', async () => {
  serve({ today: [today(SHORT, 5)] })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  expect(screen.getByRole('heading', { name: 'Jump squat' })).toBeInTheDocument()
  expect(screen.getByText('ON ITS OWN')).toBeInTheDocument() // its partner was dropped
  expect(screen.queryByRole('button', { name: 'Do Calf raise first' })).not.toBeInTheDocument()
  // Two sets in all, both jump squat: "Set 1 of 2" in the session and of the exercise.
  expect(screen.getAllByText('Set 1 of 2')).toHaveLength(2)
  fireEvent.click(button('Confirm set'))
  fireEvent.click(await screen.findByRole('button', { name: 'Skip rest' }))
  expect(await screen.findAllByText('Set 2 of 2')).toHaveLength(2)
  fireEvent.click(button('Confirm set'))
  expect(await screen.findByRole('heading', { name: 'Check and save' })).toBeInTheDocument()
  expect(screen.getByText('Jump squat')).toBeInTheDocument()
  expect(screen.queryByText('Calf raise')).not.toBeInTheDocument()
  expect(screen.queryByText('Plank')).not.toBeInTheDocument()
})

test('a session with no warm-up says nothing about one', async () => {
  serve({ today: [today({ ...SHORT, length: { ...SHORT.length!, warm_up: 'none' } })] })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.queryByText(/Warm/)).not.toBeInTheDocument()
})

test('a recovery session shows no choice', async () => {
  const recovery = { ...SESSION, kind: 'recovery' as const, warm_up: false, length: null }
  serve({ today: [today(recovery)] })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Short on time today?' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '30 min' })).not.toBeInTheDocument()
})

test('a refused choice, a failure and a lost sign-in say so and change nothing', async () => {
  serve({
    length: [
      Response.json({ detail: 'this session runs as planned' }, { status: 422 }),
      new Response(null, { status: 500 }),
      new Response(null, { status: 401 }),
    ],
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: '40 min' }))
  expect(await screen.findByText("That length can't be used for this session.")).toBeInTheDocument()
  fireEvent.click(button('40 min'))
  expect(
    await screen.findByText("Couldn't change the length. Check your connection and try again."),
  ).toBeInTheDocument()
  fireEvent.click(button('40 min'))
  expect(await screen.findByText(/Your sign-in has ended/)).toBeInTheDocument()
  expect(button('As planned')).toHaveAttribute('aria-pressed', 'true')
})

test("today's session failing to load says so", async () => {
  serve({ today: 'error' })
  render(<SessionPage />)
  expect(
    await screen.findByText("Couldn't load today's session. Check your connection."),
  ).toBeInTheDocument()
  expect(screen.queryByText('Short on time today?')).not.toBeInTheDocument()
})

test('a conditioning day logs its run at the shortened minutes once a length is chosen', async () => {
  const run = { ...item('zone2', 'Zone 2 run', null, [30]), unit: 'minutes' as const }
  const conditioning: Guided = {
    ...SESSION,
    name: 'Run + core',
    kind: 'conditioning',
    warm_up: false,
    minutes: 45,
    items: [run, item('plank', 'Plank', null, [30, 30])],
    order: [{ item: 1, set_no: 1, target: 30, rest_seconds: 60, switch: false }],
    length: { ...PLANNED, warm_up: 'none' },
  }
  const shorter: Guided = {
    ...conditioning,
    minutes: 20,
    items: [{ ...run, targets: [12] }, item('plank', 'Plank', null, [30])],
    length: { ...PLANNED, minutes: 20, warm_up: 'none' },
  }
  const plan = (target: number): CardioOptions => ({
    planned: { kind: 'zone2', session: 'Run + core', target },
    activities: ['walk'],
    week: emptyWeek({}),
  })
  serve({
    today: [today(conditioning, 1)],
    length: [Response.json(today(shorter, 2))],
    cardio: [plan(30), plan(12)],
  })
  render(<SessionPage />)
  expect(await screen.findByRole('button', { name: 'Done as planned: 30 min' })).toBeVisible()
  fireEvent.click(button('20 min'))
  expect(await screen.findByRole('button', { name: 'Done as planned: 12 min' })).toBeVisible()
  expect(screen.getByText('Target 12 min')).toBeInTheDocument()
})

test('time per session shows as chosen, from the setting, with As planned still a choice', async () => {
  const mine = { ...SHORT, length: { ...SHORT.length!, from_setting: true } }
  const sent = serve({ today: [today(mine, 4)], length: [Response.json(today(SESSION, 5))] })
  render(<SessionPage />)
  expect(await screen.findByRole('button', { name: '20 min' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(
    screen.getByText(
      '20 min is your time per session, set on Account: about 18 min, warm-up included. As planned today: about 49 min.',
    ),
  ).toBeInTheDocument()
  expect(screen.getByText('Dropped today: Plank, Calf raise.')).toBeInTheDocument()
  expect(screen.getByText('About 18 min')).toBeInTheDocument() // not "usually": a shorter day
  fireEvent.click(button('As planned'))
  expect(
    await screen.findByText('About 49 min as planned. For today only; the plan stays the same.'),
  ).toBeInTheDocument()
  expect(sent['PUT /api/session/length']).toEqual([
    { template_id: 3, place: 'home', revision: 4, first: [], minutes: null, keep: [] },
  ])
})

test('a started session at the time per session says so', async () => {
  const started = { ...SHORT, length: { ...SHORT.length!, fixed: true, from_setting: true } }
  serve({ today: [today(started, 3)] })
  render(<SessionPage />)
  expect(
    await screen.findByText(
      /20 min today \(your time per session\), about 18 min\. It stays like this now a set is kept\./,
    ),
  ).toBeInTheDocument()
})

/** At 40 min with the last-set option offered (ADR-0084): off, then on. */
const FORTY: Guided = { ...SESSION, length: { ...PLANNED, minutes: 40, last_set: false } }
const FORTY_ON: Guided = {
  ...FORTY,
  items: [SESSION.items[0], { ...SESSION.items[1], last_set_amrap: true }, SESSION.items[2]],
  length: { ...PLANNED, minutes: 40, last_set: true },
}
const lastSet = () => screen.getByRole('button', { name: /as many good reps as you can/ })

test('a shorter day offers the last set of as many good reps as you can, one tap', async () => {
  const sent = serve({ today: [today(FORTY), today(FORTY_ON)] })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(lastSet()).toHaveAttribute('aria-pressed', 'false')
  expect(
    screen.getByText("On exercises where it's safe. Stop at the first rep that isn't clean."),
  ).toBeInTheDocument()
  fireEvent.click(lastSet())
  expect(
    await screen.findByText('Saved: last set, as many good reps as you can.'),
  ).toBeInTheDocument()
  expect(sent['PATCH /api/settings']).toEqual([{ last_set_amrap: true }])
  expect(lastSet()).toHaveAttribute('aria-pressed', 'true')
  expect(lastSet()).toHaveTextContent('✓ Last set: as many good reps as you can')
})

test('turning it off says so', async () => {
  const sent = serve({ today: [today(FORTY_ON), today(FORTY)] })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: /as many good reps/ }))
  expect(await screen.findByText('Saved: last sets as usual.')).toBeInTheDocument()
  expect(sent['PATCH /api/settings']).toEqual([{ last_set_amrap: false }])
})

test('it is offered too when the shorter length is the time per session', async () => {
  const mine = { ...FORTY, length: { ...FORTY.length!, from_setting: true } }
  serve({ today: [today(mine)] })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(lastSet()).toHaveAttribute('aria-pressed', 'false')
})

test.each([
  ['as planned', { ...FORTY, length: { ...PLANNED, last_set: false } }],
  ['locked or nothing it applies to', { ...FORTY, length: { ...PLANNED, minutes: 40 } }],
  ['once a set is kept', { ...FORTY, length: { ...FORTY.length!, fixed: true } }],
])('the last set is not offered %s', async (_, session) => {
  serve({ today: [today(session)] })
  render(<SessionPage />)
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /as many good reps/ })).not.toBeInTheDocument()
})
