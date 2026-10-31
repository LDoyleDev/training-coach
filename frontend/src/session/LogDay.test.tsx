import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Clash, LogOptions, LogPlan } from '../api'
import LogDay from './LogDay'

const OPTIONS: LogOptions = {
  sessions: [
    { template_id: 1, name: 'Legs', kind: 'strength' },
    { template_id: 7, name: 'Long zone 2', kind: 'conditioning' },
  ],
  activities: ['walk', 'bike'],
}

const item = (name: string, slug: string, targets: number[], perSide = false) => ({
  slug,
  name,
  step: 'Bodyweight',
  summary: null,
  cue: null,
  unit: 'reps' as const,
  per_side: perSide,
  pair: null,
  targets,
  baseline: false,
  muscles: [],
  parts: [],
  last_set_amrap: false,
})

const LEGS: LogPlan = {
  day: '2026-10-11',
  template_id: 1,
  name: 'Legs',
  items: [item('Jump squat', 'jump-squat', [6, 6]), item('Calf raise', 'calf-raise', [12], true)],
}

const CLASH: Clash = {
  day: '2026-10-11',
  moving: false,
  recorded: [{ workout_id: 5, name: 'Legs', summary: '25 sets: Jump squat' }],
}

type Answer = Response | (() => Response)

function serve(posts: Answer[] = [], options: Answer = Response.json(OPTIONS)) {
  const sent: Record<string, unknown>[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        sent.push(JSON.parse(String(init.body)))
        const next =
          posts.shift() ??
          Response.json({ workout_id: 3, already_saved: false, next_session: 'Torso' })
        return typeof next === 'function' ? next() : next
      }
      if (path.startsWith('/api/log/plan')) return Response.json(LEGS)
      return typeof options === 'function' ? options() : options
    }),
  )
  return sent
}

// The days offered are today back two weeks, by the phone's clock.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 12, 12))
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))
const conflict = (detail: unknown) => Response.json({ detail }, { status: 409 })

async function openLegsYesterday() {
  click('Log another day')
  fireEvent.click(await screen.findByRole('button', { name: 'Yesterday' }))
  click('Legs')
  await screen.findByRole('heading', { name: 'Legs yesterday' })
}

test('a session for yesterday starts at its targets and saves what was done', async () => {
  const sent = serve()
  const onSaved = vi.fn()
  render(<LogDay onSaved={onSaved} />)
  await openLegsYesterday()
  fireEvent.click(screen.getByRole('button', { name: 'Jump squat set 2: 1 more' }))
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Calf raise set 1' }), {
    target: { value: '0' },
  })
  click('Save Legs')
  await waitFor(() =>
    expect(onSaved).toHaveBeenCalledWith('Saved Legs for yesterday. Next up: Torso.'),
  )
  expect(sent).toEqual([
    {
      token: expect.stringMatching(/^[0-9a-f]{32}$/),
      day: '2026-10-11',
      what: 'session',
      template_id: 1,
      sets: [
        { item: 0, set_no: 1, left: 6 },
        { item: 0, set_no: 2, left: 7 },
      ],
    },
  ])
})

test('a day that has its session asks, and the answer goes with the same log', async () => {
  const sent = serve([conflict(CLASH)])
  const onSaved = vi.fn()
  render(<LogDay onSaved={onSaved} />)
  await openLegsYesterday()
  click('Save Legs')
  expect(await screen.findByRole('alertdialog')).toHaveTextContent('Legs: 25 sets: Jump squat')
  click('Replace it')
  await waitFor(() => expect(onSaved).toHaveBeenCalled())
  expect(sent[1]).toEqual({ ...sent[0], resolution: 'replace', seen: [5] })
})

test('a day to move to that is taken asks for another; a changed day asks again', async () => {
  const taken: Clash = { ...CLASH, day: '2026-10-10', moving: true }
  const other: Clash = {
    ...CLASH,
    recorded: [{ workout_id: 6, name: 'Rest day', summary: 'rested' }],
  }
  serve([conflict(CLASH), conflict(taken), conflict(other)])
  render(<LogDay onSaved={() => {}} />)
  await openLegsYesterday()
  click('Save Legs')
  fireEvent.click(await screen.findByRole('button', { name: 'Move it to another day' }))
  fireEvent.click(screen.getAllByRole('button')[0])
  expect(await screen.findByText(/has Legs \(25 sets: Jump squat\) too/)).toBeInTheDocument()
  click('Back')
  click('Add to that day')
  expect(
    await screen.findByText('That day changed since you looked. Here it is now.'),
  ).toBeInTheDocument()
  expect(screen.getByRole('alertdialog')).toHaveTextContent('Rest day: rested')
  click('Cancel')
  expect(screen.getByRole('heading', { name: 'Legs yesterday' })).toBeInTheDocument()
})

test('an extra, a rest day and cardio', async () => {
  const sent = serve()
  const onSaved = vi.fn()
  render(<LogDay onSaved={onSaved} />)
  await openLegsYesterday()
  fireEvent.click(screen.getByRole('checkbox'))
  click('Save the extra')
  await waitFor(() =>
    expect(onSaved).toHaveBeenLastCalledWith(
      'Saved an extra (Legs) for yesterday. Next up: Torso.',
    ),
  )
  expect(sent[0]).toMatchObject({ what: 'extra', template_id: 1 })

  click('Log another day')
  click('Yesterday')
  click('Rest day')
  click('Save the rest day')
  await waitFor(() =>
    expect(onSaved).toHaveBeenLastCalledWith('Saved a rest day for yesterday. Next up: Torso.'),
  )
  expect(sent[1]).toEqual({ token: expect.any(String), day: '2026-10-11', what: 'rest' })

  click('Log another day')
  click('Sat 10 Oct')
  click('Cardio or HIIT')
  click('HIIT')
  click('Bike')
  click('Rounds: 1 more')
  click('Save 9 rounds')
  await waitFor(() =>
    expect(onSaved).toHaveBeenLastCalledWith('Saved cardio for Sat 10 Oct. Next up: Torso.'),
  )
  expect(sent[2]).toMatchObject({ what: 'cardio', cardio: 'hiit', value: 9, activity: 'bike' })
})

test('today offers no rest day: that is Rest today', async () => {
  serve()
  render(<LogDay onSaved={() => {}} />)
  click('Log another day')
  fireEvent.click(await screen.findByRole('button', { name: 'Today' }))
  expect(screen.getByRole('heading', { name: 'What did you do today?' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Rest day' })).toBeNull()
  click('Back')
  click('Cancel')
  expect(screen.getByRole('button', { name: 'Log another day' })).toBeInTheDocument()
})

test('every set at 0 is nothing to save, and a refusal says why', async () => {
  const sent = serve([
    Response.json({ detail: 'Sun 27 Sep is more than 14 days ago' }, { status: 422 }),
  ])
  render(<LogDay onSaved={() => {}} />)
  await openLegsYesterday()
  for (const box of screen.getAllByRole('spinbutton'))
    fireEvent.change(box, { target: { value: '0' } })
  click('Save Legs')
  expect(screen.getByRole('status')).toHaveTextContent('Enter at least one set')
  expect(sent).toEqual([])
  fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '5' } })
  click('Save Legs')
  expect(await screen.findByText('Sun 27 Sep is more than 14 days ago')).toBeInTheDocument()
})

test('signed out, offline and a changed plan each say so', async () => {
  serve(
    [
      () => new Response(null, { status: 401 }),
      conflict('stale'),
      () => new Response(null, { status: 500 }),
    ],
    new Response(null, { status: 401 }),
  )
  const { unmount } = render(<LogDay onSaved={() => {}} />)
  click('Log another day')
  expect(await screen.findByText(/sign-in has ended/i)).toBeInTheDocument()
  unmount()

  serve([
    () => new Response(null, { status: 401 }),
    conflict('changed'),
    () => new Response(null, { status: 500 }),
  ])
  render(<LogDay onSaved={() => {}} />)
  await openLegsYesterday()
  click('Save Legs')
  expect(await screen.findByText(/sign-in has ended/i)).toBeInTheDocument()
  click('Save Legs')
  expect(await screen.findByText('The plan changed meanwhile. Start again.')).toBeInTheDocument()
  click('Save Legs')
  expect(
    await screen.findByText("Couldn't save. Check your connection and try again."),
  ).toBeInTheDocument()
})

test('a plan that does not load says so', async () => {
  serve([], new Response(null, { status: 500 }))
  render(<LogDay onSaved={() => {}} />)
  click('Log another day')
  expect(
    await screen.findByText("Couldn't load your plan. Check your connection and try again."),
  ).toBeInTheDocument()
})
