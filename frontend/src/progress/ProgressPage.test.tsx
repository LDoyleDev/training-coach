import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Standing } from '../api'
import { amount, trend } from './logic'
import ProgressPage from './ProgressPage'

const make = (over: Partial<Standing>): Standing => ({
  exercise: 'Pull-up',
  unit: 'reps',
  step: 'Strict',
  step_number: 2,
  steps: 4,
  last: [],
  best_set: null,
  status: 'hold',
  retired: false,
  recent: [],
  ...over,
})

function serve(answer: Standing[] | 401 | 500) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      typeof answer === 'number' ? new Response(null, { status: answer }) : Response.json(answer),
    ),
  )
}

afterEach(() => vi.unstubAllGlobals())

test('each exercise shows its step, last session, best and status', async () => {
  serve([
    make({ last: [9, 8, 7], best_set: 10, status: 'ready', recent: [9, 10, 7] }),
    make({ exercise: 'Dead hang', unit: 'seconds', last: [45], best_set: 45, recent: [45] }),
    make({ exercise: 'Zone 2', unit: 'minutes', status: 'top_of_ladder' }),
    make({ exercise: 'Goblet squat', retired: true, last: [16], best_set: 16 }),
  ])
  render(<ProgressPage />)
  expect(await screen.findByText('Last 9 · 8 · 7 · best 10')).toBeInTheDocument()
  expect(screen.getByText('Ready to move up')).toBeInTheDocument()
  expect(screen.getByText(/1 ready to move up/)).toBeInTheDocument()
  expect(screen.getByText('Last 45 s · best 45 s')).toBeInTheDocument()
  expect(screen.getByText('Not logged at this step yet')).toBeInTheDocument()
  expect(screen.getByText('Top of the ladder')).toBeInTheDocument()
  expect(screen.getByText('(retired)')).toBeInTheDocument()
  expect(screen.getAllByText('Strict · step 2 of 4')).toHaveLength(4)
  // A trend needs two sessions or more.
  expect(screen.getAllByRole('img')).toHaveLength(1)
  expect(screen.getByRole('img', { name: 'Best set, last 3 sessions' })).toBeInTheDocument()
})

test('the trend runs oldest to newest and fits the box', () => {
  expect(trend([10, 5])).toBe('0.0,30.0 120.0,2.0') // 5 then 10: rising
  expect(trend([7, 7])).toBe('0.0,30.0 120.0,30.0') // flat
  expect(trend([7])).toBe('')
  expect(amount(make({ unit: 'minutes' }), 45)).toBe('45 min')
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
