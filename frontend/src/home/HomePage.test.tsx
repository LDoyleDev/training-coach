import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Home } from '../api'
import HomePage from './HomePage'
import { day } from './logic'

const make = (over: Partial<Home> = {}): Home => ({
  totals: {
    sessions: 42,
    sets: 1234,
    reps: 9876,
    cardio_minutes: 600,
    first_day: '2026-09-01',
    days: 40,
  },
  week: {
    start: '2026-10-05',
    done: 3,
    planned: 7,
    extras: 1,
    zone2_minutes: 90,
    zone2_target: [180, 200],
  },
  progress: {
    steps_climbed: 5,
    ready: [{ exercise: 'Pull-up', slug: 'pull-up' }],
    bests: ['Dip (chairs)'],
  },
  recent: [
    { day: '2026-10-10', session: 'Torso + neck' },
    { day: '2026-10-08', session: 'Extra' },
  ],
  today: 'Legs',
  today_minutes: 45,
  today_usual_minutes: null,
  ...over,
})

function serve(answer: Home | 401 | 500) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      typeof answer === 'number' ? new Response(null, { status: answer }) : Response.json(answer),
    ),
  )
}

afterEach(() => vi.unstubAllGlobals())

test('totals first, then progress and the week, then the button to today', async () => {
  serve(make())
  render(<HomePage />)
  expect(await screen.findByRole('heading', { name: "What you've done" })).toBeInTheDocument()
  expect(screen.getByText('42')).toBeInTheDocument()
  expect(screen.getByText('1,234')).toBeInTheDocument()
  expect(screen.getByText('9,876')).toBeInTheDocument()
  expect(screen.getByText('cardio minutes')).toBeInTheDocument()
  expect(screen.getByText(/Training since Tue 1 Sept?, 40 days ago/)).toBeInTheDocument()
  expect(screen.getByText('ladder steps climbed', { exact: false })).toBeInTheDocument()
  expect(screen.getByText(/Ready to move up:/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Pull-up' })).toHaveAttribute(
    'href',
    '/plan?move=pull-up',
  )
  expect(screen.getByText('Personal bests this week: Dip (chairs)')).toBeInTheDocument()
  expect(screen.getByText('3 of 7 sessions done · 1 extra')).toBeInTheDocument()
  expect(screen.getByText('Zone 2: 90 of 180–200 min')).toBeInTheDocument()
  expect(screen.getByRole('meter', { name: 'Zone 2 minutes this week' })).toHaveAttribute(
    'aria-valuenow',
    '90',
  )
  expect(screen.getByText('Torso + neck')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Today: Legs · about 45 min' })).toHaveAttribute(
    'href',
    '/session',
  )
  const main = screen.getByRole('main')
  expect(main.querySelector('a[href="/progress"]')).toHaveTextContent('Progress')
  expect(main.querySelector('a[href="/plan"]')).toHaveTextContent('Plan')
})

test('before the first session, and with nothing left today', async () => {
  serve(
    make({
      totals: { sessions: 0, sets: 0, reps: 0, cardio_minutes: 0, first_day: null, days: 0 },
      week: {
        start: '2026-10-05',
        done: 0,
        planned: 7,
        extras: 0,
        zone2_minutes: 0,
        zone2_target: null,
      },
      progress: { steps_climbed: 1, ready: [], bests: [] },
      recent: [],
      today: null,
      today_minutes: null,
    }),
  )
  render(<HomePage />)
  expect(
    await screen.findByRole('heading', { name: 'Your first session is waiting' }),
  ).toBeInTheDocument()
  expect(screen.queryByText(/Since/)).not.toBeInTheDocument()
  expect(screen.getByText('ladder step climbed', { exact: false })).toBeInTheDocument()
  expect(screen.queryByText(/Ready to move up/)).not.toBeInTheDocument()
  expect(screen.getByText('Zone 2: 0 min')).toBeInTheDocument()
  expect(screen.queryByRole('meter')).not.toBeInTheDocument()
  expect(screen.getByText('Nothing logged in the last seven days.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Go to today' })).toHaveAttribute('href', '/session')
})

test('the button says how long today usually takes, once it has been timed', async () => {
  serve(make({ today_usual_minutes: 38 }))
  render(<HomePage />)
  expect(await screen.findByRole('link', { name: 'Today: Legs · usually 38 min' })).toBeVisible()
})

test('a test day has no length', async () => {
  serve(make({ today: 'Retest, day 1', today_minutes: null }))
  render(<HomePage />)
  expect(await screen.findByRole('link', { name: 'Today: Retest, day 1' })).toBeVisible()
})

test('signed out, or the server down', async () => {
  serve(401)
  const { unmount } = render(<HomePage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  unmount()
  serve(500)
  render(<HomePage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your training.")
})

test('a day reads as the local date it names', () => {
  expect(day('2026-10-11')).toMatch(/^Sun 11 Oct/)
})
