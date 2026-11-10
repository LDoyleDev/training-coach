import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Coverage, FittedSession, Preview, WalkLadder, Walkthrough } from '../api'
import type { Draft, Known } from './flow'
import { NOTHING_ANSWERED } from './level'
import { PlanScreen } from './PlanScreen'

const step = (
  id: number,
  name: string,
  level: number,
  more: Partial<WalkLadder['steps'][0]> = {},
) => ({
  id,
  position: id % 10,
  name,
  level,
  question: id % 10 ? `Can you do ${name}?` : null,
  cue: null,
  needs: [],
  marks: [],
  ...more,
})
const PUSH: WalkLadder = {
  slug: 'push-up',
  name: 'Push-up',
  on: null,
  steps: [
    step(10, 'Wall', 1),
    step(11, 'Counter', 2),
    step(12, 'Table', 3),
    step(13, 'Floor', 4, { marks: ['floor'] }),
  ],
}
const SPLIT: WalkLadder = {
  slug: 'bulgarian-split-squat',
  name: 'Bulgarian split squat',
  on: null,
  steps: [step(20, 'Holding a chair', 2), step(21, 'Low step', 3)],
}
const TIB: WalkLadder = {
  slug: 'tibialis-raise',
  name: 'Tibialis raise',
  on: null,
  steps: [step(30, 'Wall', 1)],
}
const KNOWN: Known = {
  consent: false,
  residence: false,
  safety: false,
  ladders: [PUSH, SPLIT, TIB],
}

const item = (exercise: string, name: string) => ({
  exercise,
  name,
  sets: 3,
  rep_min: 8,
  rep_max: 15,
  per_side: false,
  pair: null,
})
const session = (slug: string, name: string, rest_after: number) => ({
  slug,
  name,
  focus: '',
  rest_after,
  items: [item('push-up', 'Push-up'), item('bulgarian-split-squat', 'Bulgarian split squat')],
})
const STARTERS: Walkthrough['starters'] = [
  {
    slug: 'two-days',
    name: '2 days a week',
    days: 2,
    sessions: [session('a2', 'A', 2), session('b2', 'B', 3)],
  },
  {
    slug: 'three-days',
    name: '3 days a week',
    days: 3,
    sessions: [
      session('a', 'Full body A', 1),
      session('b', 'Full body B', 1),
      session('c', 'Full body C', 2),
    ],
  },
  {
    slug: 'four-days',
    name: '4 days a week',
    days: 4,
    sessions: [
      { ...session('l1', 'Lower 1', 0), items: [item('tibialis-raise', 'Tibialis raise')] },
      session('u1', 'Upper 1', 1),
      session('l2', 'Lower 2', 0),
      session('u2', 'Upper 2', 2),
    ],
  },
]

const DRAFT: Draft = {
  about: NOTHING_ANSWERED,
  safety: {},
  avoid: {
    avoid_floor: false,
    avoid_kneeling: false,
    avoid_impact: false,
    avoid_hanging: false,
    avoid_knees: false,
  },
  places: 'home',
  kit: null,
  placement: {},
  days: [0, 2, 4],
  minutes: 20,
  count: null,
  chosen: {},
  putBack: false,
}

const COVERAGE = (place: 'home' | 'gym'): Coverage => ({
  place,
  places: 'both',
  muscles: [],
  sessions: [],
  main_on_target: place === 'home' ? 3 : 7,
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
})
const fitted = (place: 'home' | 'gym', on: string, slug: string, name: string): FittedSession => ({
  slug,
  name,
  focus: '',
  rest_after: 1,
  on,
  home: {
    place: 'home',
    minutes: 19,
    fits: true,
    dropped: ['Bulgarian split squat'],
    items: [
      { ...item('push-up', 'Push-up'), step: 'Counter', kept: 3 },
      {
        ...item('bulgarian-split-squat', 'Bulgarian split squat'),
        step: 'Holding a chair',
        kept: 0,
      },
    ],
  },
  gym:
    place === 'gym'
      ? {
          place: 'gym',
          minutes: 25,
          fits: true,
          dropped: [],
          items: [{ ...item('bench', 'Bench press'), step: 'Barbell', kept: 3 }],
        }
      : null,
})
const PREVIEW = (place: 'home' | 'gym' = 'home'): Preview => ({
  sessions: [
    fitted(place, '2026-11-09', 'a', 'Full body A'),
    fitted(place, '2026-11-11', 'b', 'Full body B'),
    fitted(place, '2026-11-13', 'c', 'Full body C'),
  ],
  week: ['09', '10', '11', '12', '13', '14', '15'].map((d) => ({
    date: `2026-11-${d}`,
    session: { '09': 'a', '11': 'b', '13': 'c' }[d] ?? null,
  })),
  coverage: place === 'gym' ? [COVERAGE('home'), COVERAGE('gym')] : [COVERAGE('home')],
})

type Call = [string, Record<string, unknown>]
function serve({ preview = () => Response.json(PREVIEW()) }: { preview?: () => Response } = {}) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      calls.push([path, JSON.parse(String(init?.body))])
      return preview()
    }),
  )
  return calls
}
const previews = (calls: Call[]) =>
  calls.filter(([p]) => p === '/api/walkthrough/preview').map(([, b]) => b)

/** The screen, its draft changed as StartPage changes it. */
function show({ draft = DRAFT, who = 'member' }: { draft?: Draft; who?: Walkthrough['who'] } = {}) {
  let current = draft
  const view = () => (
    <PlanScreen
      who={who}
      known={KNOWN}
      starters={STARTERS}
      draft={current}
      onChange={(next) => {
        current = next
        rerender(view())
      }}
    />
  )
  const { rerender } = render(view())
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 10, 9, 10, 0)) // a Monday
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const tap = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

test('the plan the walk makes: the week, each session trimmed, the steps and the map', async () => {
  const calls = serve()
  show()
  expect(await screen.findByText('Mon 9 Nov')).toBeInTheDocument()
  expect(screen.getByText(/3 days a week, from today/)).toBeInTheDocument()
  expect(screen.getAllByText('Rest')).toHaveLength(4)
  const a = screen.getByRole('heading', { name: /Full body A/ }).closest('section')!
  expect(within(a).getByText('Push-up: Counter, 3 sets')).toBeInTheDocument()
  expect(
    within(a).getByText(/About 19 minutes. Dropped to fit: Bulgarian split squat./),
  ).toBeInTheDocument()
  expect(screen.getByText('3 of 10 main muscles on target')).toBeInTheDocument()
  expect(screen.queryByText(/doesn't get a session/)).not.toBeInTheDocument()
  // The outcomes only: the 3-day from today, the walk's steps (the bottom, nothing asked).
  expect(previews(calls)).toEqual([
    {
      starter: 'three-days',
      steps: { 'push-up': 10, 'bulgarian-split-squat': 20, 'tibialis-raise': 30 },
      starts_on: '2026-11-09',
      places: 'home',
      kit: null,
      avoid: [],
      session_minutes: 20,
      session_exercises: null,
      left_out: [],
    },
  ])
  expect(screen.queryByRole('combobox', { name: /Tibialis raise/ })).not.toBeInTheDocument() // not in the 3-day
})

test('a change re-asks for the plan: days, minutes, count and a step, open steps only', async () => {
  const calls = serve()
  show({
    draft: {
      ...DRAFT,
      avoid: { ...DRAFT.avoid, avoid_floor: true },
      about: { ...NOTHING_ANSWERED, often: 'under_weekly' }, // level 2: the counter first
      placement: { 'push-up': ['yes', 'no'] },
    },
  })
  await screen.findByText('Mon 9 Nov')
  const push = screen.getByRole('combobox', { name: 'Push-up' })
  expect(push).toHaveValue('11') // the counter: Yes there, No to the table
  expect(within(push).queryByRole('option', { name: 'Floor' })).not.toBeInTheDocument() // off the floor
  fireEvent.change(push, { target: { value: '12' } })
  tap('Tuesday')
  tap('40 minutes')
  tap('6')
  await vi.waitFor(() =>
    expect(previews(calls).at(-1)).toMatchObject({
      starter: 'four-days',
      steps: { 'push-up': 12 },
      avoid: ['floor'],
      session_minutes: 40,
      session_exercises: 6,
    }),
  )
})

test("tapped days the pattern can't reach are named", async () => {
  serve()
  show({ draft: { ...DRAFT, days: [0, 1, 2, 4] } })
  expect(
    await screen.findByText("Tuesday doesn't get a session, to keep the rest days between them."),
  ).toBeInTheDocument()
})

test('5 days or more: the cardio note, not the days without a session', async () => {
  serve()
  show({ draft: { ...DRAFT, days: [0, 1, 2, 3, 4] } })
  expect(await screen.findByText(/150 minutes a week/)).toBeInTheDocument()
  expect(screen.queryByText(/get a session/)).not.toBeInTheDocument()
})

test("a day tapped while the next plan loads isn't named as missed yet", async () => {
  let answer: (r: Response) => void = () => {}
  serve()
  show()
  await screen.findByText('Mon 9 Nov')
  vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)))
  tap('Saturday')
  expect(screen.getByRole('status')).toHaveTextContent('Making your plan…')
  expect(screen.queryByText(/Saturday doesn't get a session/)).not.toBeInTheDocument()
  answer(Response.json(PREVIEW()))
  expect(await screen.findByText(/Saturday doesn't get a session/)).toBeInTheDocument()
})

test.each([
  [[0], /One day a week gets the 2-day plan.*you do A one week and B the next/],
  [[0, 1, 2, 3, 4], /5 days a week get the 4-day plan.*150 minutes a week/],
])('the notes for %j', async (days, note) => {
  serve()
  show({ draft: { ...DRAFT, days } })
  expect(await screen.findByText(note)).toBeInTheDocument()
})

test('65 and over: the balance and sit-to-stand line, nothing tracked', async () => {
  serve()
  show({ draft: { ...DRAFT, about: { ...NOTHING_ANSWERED, age: '75+' } } })
  expect(
    await screen.findByText(/a balance and sit-to-stand snack.*It isn't tracked here/),
  ).toBeInTheDocument()
})

test('level 1 leaves the split squat out, and it can be put back', async () => {
  const calls = serve()
  show({ draft: { ...DRAFT, about: { ...NOTHING_ANSWERED, chair: false } } })
  expect(await screen.findByText(/Left out for now: the Bulgarian split squat/)).toBeInTheDocument()
  expect(previews(calls)[0].left_out).toEqual(['bulgarian-split-squat'])
  tap('Put it back')
  expect(screen.getByText('The Bulgarian split squat is back in.')).toBeInTheDocument()
  await vi.waitFor(() => expect(previews(calls).at(-1)?.left_out).toEqual([]))
  tap('Leave it out')
  expect(screen.getByText(/Left out for now: the/)).toBeInTheDocument()
})

test('at both, each session at home and at the gym, and the map for each', async () => {
  serve({ preview: () => Response.json(PREVIEW('gym')) })
  show({ draft: { ...DRAFT, places: 'both' } })
  await screen.findByText('Mon 9 Nov')
  const a = screen.getByRole('heading', { name: /Full body A/ }).closest('section')!
  expect(within(a).getByText('At home')).toBeInTheDocument()
  expect(within(a).getByText('Bench press: Barbell, 3 sets')).toBeInTheDocument()
  expect(screen.getByText('3 of 10 main muscles on target')).toBeInTheDocument()
  tap(/Gym/)
  expect(screen.getByText('7 of 10 main muscles on target')).toBeInTheDocument()
})

test('gym only: the gym version, and no home kit sent', async () => {
  const calls = serve({ preview: () => Response.json(PREVIEW('gym')) })
  show({
    draft: {
      ...DRAFT,
      places: 'gym',
      kit: [{ kit: 'mat', kg: null, min_kg: null, resistance: null, note: '' }],
    },
  })
  await screen.findByText('Mon 9 Nov')
  expect(screen.queryByText('At home')).not.toBeInTheDocument()
  expect(screen.getAllByText('Bench press: Barbell, 3 sets')).toHaveLength(3)
  expect(previews(calls)[0].kit).toBeNull()
})

test.each([
  ['owner_try_out', "This is a try-out: your plan won't change."],
  ['member', 'Saving it comes in the next version. Nothing was saved.'],
] as const)('%s: the plan, and nothing saved', async (who, said) => {
  serve()
  show({ who })
  await screen.findByText('Mon 9 Nov')
  expect(screen.getByText(said)).toBeInTheDocument()
})

test.each([
  [
    () => Response.json({ detail: 'Push-up: Floor is locked.' }, { status: 422 }),
    'Push-up: Floor is locked.',
  ],
  [() => new Response(null, { status: 500 }), "Couldn't make your plan."],
])('a preview that is refused or fails says so', async (preview, said) => {
  serve({ preview })
  show()
  expect(await screen.findByRole('alert')).toHaveTextContent(said)
  expect(screen.queryByText('Mon 9 Nov')).not.toBeInTheDocument()
})

test('after a refused preview, a change says the next plan is on its way', async () => {
  let answer: (r: Response) => void = () => {}
  serve({ preview: () => Response.json({ detail: 'Push-up: Floor is locked.' }, { status: 422 }) })
  show()
  expect(await screen.findByRole('alert')).toHaveTextContent('Push-up: Floor is locked.')
  vi.mocked(fetch).mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)))
  tap('30 minutes')
  expect(screen.getByRole('status')).toHaveTextContent('Making your plan…')
  answer(Response.json(PREVIEW()))
  expect(await screen.findByText('Mon 9 Nov')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('while the next plan loads, the last one stays and says it is being made', async () => {
  let answer: (r: Response) => void = () => {}
  const calls = serve()
  show()
  await screen.findByText('Mon 9 Nov')
  vi.mocked(fetch).mockImplementationOnce(
    (_path, init) =>
      new Promise((resolve) => {
        calls.push(['/api/walkthrough/preview', JSON.parse(String(init?.body))])
        answer = resolve
      }),
  )
  tap('30 minutes')
  expect(screen.getByRole('status')).toHaveTextContent('Making your plan…')
  expect(screen.getByText('Mon 9 Nov')).toBeInTheDocument()
  answer(Response.json(PREVIEW()))
  await vi.waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
})
