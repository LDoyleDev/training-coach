import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { DayLog, Habits } from '../api'
import DayCard from './DayCard'

const TODAY = '2026-10-23'

const HABITS: Habits = {
  day: TODAY,
  week_days: 5,
  habits: [{ key: 'protein', label: 'Protein', hint: 'Enough.', done: false, week_done: 2 }],
}

function logged(day: string): DayLog {
  if (day !== TODAY) return { day, today: TODAY, first: '2026-10-21', workouts: [] }
  return {
    day,
    today: TODAY,
    first: '2026-10-21',
    workouts: [
      {
        workout_id: 23,
        name: 'Cardio + core',
        status: 'done',
        planned: true,
        activity: null,
        band: { minutes: 43, avg_hr: 139, max_hr: 160 },
        exercises: [
          {
            name: 'Moderate cardio',
            unit: 'minutes',
            step: '',
            sets: [{ set_no: 1, left: 43, right: null }],
          },
          {
            name: 'Copenhagen plank',
            unit: 'reps',
            step: 'Knee on a chair',
            sets: [
              { set_no: 1, left: 12, right: 11 },
              { set_no: 2, left: 12, right: 12 },
            ],
          },
          {
            name: 'Dead hang',
            unit: 'seconds',
            step: 'Two hands',
            sets: [{ set_no: 1, left: 45, right: null }],
          },
        ],
      },
      {
        workout_id: 24,
        name: 'Extra',
        status: 'done',
        planned: false,
        activity: 'walk',
        band: null,
        exercises: [],
      },
    ],
  }
}

/** A fake API: /api/day answers per ``on`` (or fails), /api/habits answers HABITS. */
function serve(day: 'ok' | 'fail' | 'fail-earlier' | 'signed-out' = 'ok') {
  const fetchMock = vi.fn(async (path: string) => {
    if (path.startsWith('/api/habits')) return Response.json(HABITS)
    if (day === 'signed-out') return new Response(null, { status: 401 })
    if (day === 'fail') return new Response(null, { status: 500 })
    const on = new URL(path, 'https://coach.example.com').searchParams.get('on') ?? TODAY
    if (day === 'fail-earlier' && on !== TODAY) return new Response(null, { status: 500 })
    return Response.json(logged(on))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

test("shows today's log with steps, sides, units and the band's numbers", async () => {
  serve()
  render(<DayCard />)
  const section = await screen.findByRole('region', { name: 'Logged today' })
  const view = within(section)
  expect(view.getByRole('heading', { name: 'Cardio + core' })).toBeInTheDocument()
  expect(view.getByText('Band: 43 min · avg 139 bpm · max 160')).toBeInTheDocument()
  expect(view.getByText(/: 43 min$/)).toBeInTheDocument()
  expect(view.getByText(/: 12\/11 · 12\/12$/)).toBeInTheDocument()
  expect(view.getByText('(Knee on a chair)')).toBeInTheDocument()
  expect(view.getByText(/: 45 s$/)).toBeInTheDocument()
  expect(view.getByRole('heading', { name: 'Extra: walk' })).toBeInTheDocument()
  expect(view.getByRole('button', { name: 'Next day' })).toBeDisabled()
  expect(await screen.findByRole('heading', { name: 'Habits today' })).toBeInTheDocument()
})

test('steps back a day at a time to the first day, and the date returns to today', async () => {
  const fetchMock = serve()
  render(<DayCard />)
  fireEvent.click(await screen.findByRole('button', { name: 'Previous day' }))
  expect(await screen.findByRole('button', { name: 'Logged Yesterday: back to today' }))
  expect(screen.getByText('Nothing logged.')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/api/day?on=2026-10-22', expect.anything())
  expect(screen.queryByRole('heading', { name: /Habits/ })).not.toBeInTheDocument() // today's only

  fireEvent.click(screen.getByRole('button', { name: 'Previous day' }))
  const first = await screen.findByRole('button', { name: /Logged Wed 21 Oct: back to today/ })
  expect(screen.getByRole('button', { name: 'Previous day' })).toBeDisabled() // the first day

  fireEvent.click(first)
  expect(await screen.findByRole('region', { name: 'Logged today' })).toBeInTheDocument()
})

test('the arrow keys step days too', async () => {
  serve()
  render(<DayCard />)
  const back = await screen.findByRole('button', { name: 'Previous day' })
  fireEvent.keyDown(back, { key: 'ArrowLeft' })
  const date = await screen.findByRole('button', { name: /Yesterday: back to today/ })
  fireEvent.keyDown(date, { key: 'ArrowRight' })
  expect(await screen.findByRole('region', { name: 'Logged today' })).toBeInTheDocument()
})

test("signed out, there's no day card, but today's habits still load", async () => {
  serve('signed-out')
  render(<DayCard />)
  expect(await screen.findByRole('heading', { name: 'Habits today' })).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: /Logged/ })).not.toBeInTheDocument()
})

test("a first load that fails says so and keeps today's habits (review of #298)", async () => {
  serve('fail')
  render(<DayCard />)
  expect(await screen.findByRole('status')).toHaveTextContent("Couldn't reach the coach")
  expect(await screen.findByRole('heading', { name: 'Habits today' })).toBeInTheDocument()
})

test('a day that fails to load says so and keeps the last one', async () => {
  serve('fail-earlier')
  render(<DayCard />)
  fireEvent.click(await screen.findByRole('button', { name: 'Previous day' }))
  expect(await screen.findByRole('status')).toHaveTextContent("Couldn't reach the coach")
  expect(screen.getByRole('region', { name: 'Logged today' })).toBeInTheDocument()
})
