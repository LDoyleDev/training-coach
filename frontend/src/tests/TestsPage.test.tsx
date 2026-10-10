import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { FitnessTest, TestDay, TestDayDue } from '../api'
import TestsPage from './TestsPage'

const TESTS: FitnessTest[] = [
  {
    slug: 'max-pull-ups',
    name: 'Max pull-ups',
    day: 1,
    unit: 'reps',
    per_side: false,
    cue: 'Chin over the bar.',
    low: 0,
    high: 500,
  },
  {
    slug: 'dead-hang',
    name: 'Dead hang',
    day: 1,
    unit: 'seconds',
    per_side: false,
    cue: 'Arms straight.',
    low: 0,
    high: 3600,
  },
  {
    slug: 'split-squat',
    name: 'Bulgarian split squat',
    day: 2,
    unit: 'reps',
    per_side: true,
    cue: 'Back foot on a chair.',
    low: 0,
    high: 500,
  },
]

const DONE: TestDay = {
  id: 1,
  on: '2026-10-01',
  day: 1,
  time_of_day: 'morning',
  fed: false,
  slept_well: true,
  results: [{ test: 'max-pull-ups', side: 'both', value: 7 }],
}

type Server = {
  days?: TestDay[]
  after?: TestDay[] // the days listed once a save went through
  due?: TestDayDue
  signedIn?: boolean
  save?: 'refuse' | 'fail'
}

/** A fake API; returns the bodies of the saves sent. */
function serve(server: Server = {}) {
  const sent: unknown[] = []
  let saved = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (server.signedIn === false) return new Response(null, { status: 401 })
      if (init?.method === 'POST') {
        sent.push(JSON.parse(String(init.body)))
        if (server.save === 'refuse')
          return Response.json({ detail: 'max-pull-ups is in twice' }, { status: 422 })
        if (server.save === 'fail') return new Response(null, { status: 500 })
        saved = true
        return Response.json({ id: 2, already_saved: false })
      }
      if (path === '/api/tests') return Response.json(TESTS)
      if (path === '/api/tests/due') return Response.json(server.due ?? null)
      return Response.json(saved && server.after ? server.after : (server.days ?? []))
    }),
  )
  return sent
}

const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }))

afterEach(() => vi.unstubAllGlobals())

test('day 1: conditions, each test, then save once', async () => {
  const sent = serve({ days: [DONE] })
  render(<TestsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start day 1 tests' }))
  click('Fasted')
  click('Morning')
  click('Start the tests')
  expect(screen.getByRole('heading', { name: 'Max pull-ups' })).toBeInTheDocument()
  expect(screen.getByText('Last time: 7')).toBeInTheDocument()
  expect(screen.getByRole('textbox')).toHaveValue('7') // starts from last time
  click('1 more')
  click('Next')
  expect(screen.getByRole('heading', { name: 'Dead hang' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '52' } })
  click('Next')
  expect(screen.getByRole('heading', { name: 'Check and save' })).toBeInTheDocument()
  expect(screen.getByText('Dead hang: 52 s')).toBeInTheDocument()
  click('Save')
  expect(await screen.findByRole('heading', { name: 'Day 1 tests saved' })).toBeInTheDocument()
  expect(sent).toHaveLength(1)
  expect(sent[0]).toMatchObject({
    day: 1,
    time_of_day: 'morning',
    fed: false,
    slept_well: true,
    results: [
      { test: 'max-pull-ups', side: 'both', value: 8 },
      { test: 'dead-hang', side: 'both', value: 52 },
    ],
  })
})

test('a skipped test is left out, and a value out of range is caught', async () => {
  const sent = serve()
  render(<TestsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start day 1 tests' }))
  click('Start the tests')
  click('Skip')
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '99999' } })
  expect(screen.getByRole('alert')).toHaveTextContent('A whole number from 0 to 3600.')
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  click('5 less')
  expect(screen.getByRole('textbox')).toHaveValue('99994')
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '40' } })
  click('Next')
  click('Save')
  await screen.findByRole('heading', { name: 'Day 1 tests saved' })
  expect(sent[0]).toMatchObject({ results: [{ test: 'dead-hang', value: 40 }] })
  click('Done')
  expect(screen.getByRole('heading', { name: 'Baseline tests' })).toBeInTheDocument()
})

test('a one-sided test needs both sides; Back goes over a test again', async () => {
  serve()
  render(<TestsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start day 2 tests' }))
  click('Yes')
  click('No')
  click('Start the tests')
  expect(screen.getByRole('heading', { name: 'Bulgarian split squat: Left' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '12' } })
  click('Next')
  click('Skip') // the right side
  expect(screen.getByText(/one side only isn't saved/)).toBeInTheDocument()
  expect(screen.getByText(/slept badly/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  click('Back')
  expect(screen.getByRole('heading', { name: 'Bulgarian split squat: Right' })).toBeInTheDocument()
  click('Back')
  expect(screen.getByRole('textbox')).toHaveValue('12') // kept
  click('Back')
  expect(screen.getByRole('heading', { name: 'Day 2: conditions' })).toBeInTheDocument()
  click('Leave')
  expect(screen.getByRole('heading', { name: 'Baseline tests' })).toBeInTheDocument()
})

test('a refused or failed save says so and keeps the results', async () => {
  serve({ save: 'refuse' })
  render(<TestsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start day 1 tests' }))
  click('Fed')
  click('Start the tests')
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '8' } })
  click('Next')
  click('Skip')
  click('Save')
  expect(await screen.findByText('max-pull-ups is in twice')).toBeInTheDocument()
  vi.unstubAllGlobals()
  serve({ save: 'fail' })
  click('Save')
  expect(await screen.findByText(/Check your connection/)).toBeInTheDocument()
  expect(screen.getByText('Max pull-ups: 8')).toBeInTheDocument()
})

test('every test skipped leaves nothing to save', async () => {
  serve()
  render(<TestsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start day 1 tests' }))
  click('Start the tests')
  click('Skip')
  click('Skip')
  expect(screen.getByText(/nothing to save/)).toBeInTheDocument()
})

test('earlier test days are listed with their conditions', async () => {
  serve({
    days: [{ ...DONE, results: [...DONE.results, { test: 'gone', side: 'left', value: 3 }] }],
  })
  render(<TestsPage />)
  expect(
    await screen.findByText('2026-10-01 · Day 1 · morning, fasted, slept well'),
  ).toBeInTheDocument()
  expect(screen.getByText('Max pull-ups: 7')).toBeInTheDocument()
  expect(screen.getByText('gone (Left): 3')).toBeInTheDocument() // a test the plan dropped
})

test('signed out, or the server down', async () => {
  serve({ signedIn: false })
  const { unmount } = render(<TestsPage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  unmount()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  render(<TestsPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load the tests.")
})

test('after saving, each result shows against the baseline and last time', async () => {
  const first = {
    ...DONE,
    id: 1,
    on: '2026-09-29',
    results: [{ test: 'max-pull-ups', side: 'both' as const, value: 6 }],
  }
  const second = { ...DONE, id: 3, on: '2026-10-05' }
  const now: TestDay = {
    ...DONE,
    id: 2,
    on: '2026-10-10',
    fed: true,
    results: [{ test: 'max-pull-ups', side: 'both', value: 9 }],
  }
  serve({ days: [second, first], after: [now, second, first] })
  render(<TestsPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start day 1 tests' }))
  click('Fed')
  click('Start the tests')
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '9' } })
  click('Next')
  click('Skip')
  click('Save')
  expect(
    await screen.findByText('Max pull-ups: 9 · baseline 6 (+3) · last 7 (+2)'),
  ).toBeInTheDocument()
  expect(screen.getByText('Not quite comparable: fed, last time fasted.')).toBeInTheDocument()
})

test('a test day due today is offered first', async () => {
  const sent = serve({
    days: [DONE],
    due: { day: 2, name: 'Baseline tests, day 2', tests: ['Bulgarian split squat'] },
  })
  render(<TestsPage />)
  expect(await screen.findByText('Due today: Baseline tests, day 2')).toBeInTheDocument()
  click('Start baseline tests, day 2')
  expect(screen.getByRole('heading', { name: 'Day 2: conditions' })).toBeInTheDocument()
  expect(sent).toHaveLength(0)
})
