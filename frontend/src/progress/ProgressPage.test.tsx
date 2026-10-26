import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Standing } from '../api'
import { chart } from './chart'
import { amount, trend } from './logic'
import ProgressPage from './ProgressPage'

vi.mock('../App', () => ({ default: () => <p>the plan</p> }))

const make = (over: Partial<Standing>): Standing => ({
  exercise: 'Pull-up',
  unit: 'reps',
  slug: 'pull-up',
  step: 'Strict',
  step_id: 2,
  ladder: [],
  step_number: 2,
  steps: 4,
  last: [],
  best_set: null,
  status: 'hold',
  retired: false,
  trend: [],
  unlock: null,
  ...over,
})

function serve(answer: Standing[] | 401 | 500) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      if (path === '/api/progress/times') return Response.json([]) // SessionTimes' own tests
      return typeof answer === 'number'
        ? new Response(null, { status: answer })
        : Response.json({ today: '2026-10-21', standings: answer })
    }),
  )
}

afterEach(() => vi.unstubAllGlobals())

test('each exercise shows its step, last session, best and status', async () => {
  serve([
    make({
      last: [9, 8, 7],
      best_set: 10,
      status: 'ready',
      trend: [
        { day: '2026-10-01', best: 12, step_number: 1 },
        { day: '2026-10-08', best: 7, step_number: 2 },
        { day: '2026-10-15', best: 9, step_number: 2 },
      ],
    }),
    make({
      exercise: 'Dead hang',
      unit: 'seconds',
      last: [45],
      best_set: 45,
      trend: [{ day: '2026-10-15', best: 45, step_number: 1 }],
    }),
    make({ exercise: 'Zone 2', unit: 'minutes', status: 'top_of_ladder' }),
    make({ exercise: 'Goblet squat', retired: true, last: [16], best_set: 16 }),
  ])
  render(<ProgressPage />)
  expect(await screen.findByText('Last 9 · 8 · 7 · best 10')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Ready to move up' })).toHaveAttribute(
    'href',
    '/plan?move=pull-up',
  )
  expect(screen.getByRole('link', { name: '1 ready to move up' })).toHaveAttribute(
    'href',
    '/plan?move=pull-up',
  )
  expect(screen.getByText('Last 45 s · best 45 s')).toBeInTheDocument()
  expect(screen.getByText('Not logged at this step yet')).toBeInTheDocument()
  expect(screen.getByText('Top of the ladder')).toBeInTheDocument()
  expect(screen.getByText('(retired)')).toBeInTheDocument()
  expect(screen.getAllByText('Strict · step 2 of 4')).toHaveLength(4)
  const pull = screen.getByRole('img', { name: /Moved up to step 2 on 8 Oct; best 12 to 7$/ })
  expect(pull).toHaveAccessibleName(
    'Best set per session, last 6 weeks: 3 sessions, from 12 to 9' +
      '. Moved up to step 2 on 8 Oct; best 12 to 7',
  )
  expect(pull).toHaveTextContent('Step 2 ↑') // the move up, marked
  expect(pull).toHaveTextContent('Today')
  expect(screen.getByRole('img', { name: /1 session, from 45 s to 45 s$/ })).toBeInTheDocument()
  expect(screen.getAllByText('No sessions in the last 6 weeks.')).toHaveLength(2)
})

test('the trend runs oldest to newest and fits the box', () => {
  expect(trend([10, 5])).toBe('0.0,30.0 120.0,2.0') // 5 then 10: rising
  expect(trend([7, 7])).toBe('0.0,30.0 120.0,30.0') // flat
  expect(trend([7])).toBe('')
  expect(amount(make({ unit: 'minutes' }), 45)).toBe('45 min')
})

test('the graph puts sessions on their dates over six weeks, best set up the side', () => {
  const today = new Date(2026, 9, 21)
  const found = chart(
    [
      { day: '2026-09-10', best: 8, step_number: 1 }, // the window's first day
      { day: '2026-10-21', best: 12, step_number: 1 }, // today
    ],
    today,
  )
  expect(found).not.toBeNull()
  const [first, last] = found!.dots
  expect([first.x, first.y]).toEqual([34, 78]) // left edge, bottom: the lowest
  expect([last.x, last.y]).toEqual([292, 14]) // right edge, top: the highest
  expect([found!.low, found!.high]).toEqual([8, 12])
  expect(found!.start).toEqual(new Date(2026, 8, 10)) // 42 days, today included
  expect(found!.weeks).toHaveLength(7) // six weeks of gridlines, both ends
  expect(found!.periods).toHaveLength(1) // one step all along: one period
  expect(chart([], today)).toBeNull()
  // Two sessions on one day share an x, the better one higher.
  const twice = chart(
    [
      { day: '2026-10-20', best: 6, step_number: 1 },
      { day: '2026-10-20', best: 9, step_number: 1 },
    ],
    today,
  )!.dots
  expect(twice[0].x).toBe(twice[1].x)
  expect(twice[1].y).toBeLessThan(twice[0].y)
  // One value sits in the middle rather than on the floor.
  expect(chart([{ day: '2026-10-20', best: 5, step_number: 1 }], today)!.dots[0].y).toBe(46)
})

test('signed out, or the server down', async () => {
  serve(401)
  const { unmount } = render(<ProgressPage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  unmount()
  serve(500)
  render(<ProgressPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your progress.")
})

test('the plan is not a tab here any more: it has its own page', async () => {
  serve([make({})])
  render(<ProgressPage />)
  expect(await screen.findByText('Pull-up')).toBeInTheDocument()
  expect(screen.queryByRole('tab')).toBeNull()
  expect(screen.queryByText('the plan')).toBeNull()
})

test('at the top for the kit: says so, what unlocks the next, and links to My equipment', async () => {
  const ladder = [
    { id: 1, name: 'Two-hand, 8 kg', cue: null, missing: [] },
    { id: 2, name: 'Two-hand, 16 kg', cue: null, missing: ['a 16 kg kettlebell'] },
  ]
  serve([
    make({
      exercise: 'Swing',
      step: 'Two-hand, 8 kg',
      step_id: 1,
      ladder,
      status: 'top_of_ladder',
      unlock: 'a 16 kg kettlebell unlocks Two-hand, 16 kg',
    }),
    make({ exercise: 'Press', step: 'Two-hand, 16 kg', ladder }), // chosen by hand
  ])
  render(<ProgressPage />)
  expect(await screen.findByText('Top for your kit')).toBeInTheDocument()
  expect(screen.queryByText('Top of the ladder')).not.toBeInTheDocument()
  expect(screen.getByText(/A 16 kg kettlebell unlocks Two-hand, 16 kg\./)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'My equipment' })).toHaveAttribute(
    'href',
    '/account#my-equipment',
  )
  expect(
    screen.getByText('This step needs a 16 kg kettlebell, not in your kit.'),
  ).toBeInTheDocument()
})
