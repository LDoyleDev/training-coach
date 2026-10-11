import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Habits } from '../api'
import HabitsCard from './Habits'

const HABITS: Habits = {
  day: '2026-10-14',
  week_days: 3,
  habits: [
    {
      key: 'morning_light',
      label: 'Morning light',
      hint: 'Outside early.',
      done: false,
      week_done: 1,
    },
    {
      key: 'protein',
      label: 'Protein target (165 g)',
      hint: '165 g a day.',
      done: true,
      week_done: 3,
    },
    { key: 'wind_down', label: 'Wind-down', hint: 'No screens.', done: false, week_done: 0 },
  ],
}

/** A fake API: GET answers ``today``; PUT flips the habit named in the path, or fails. */
function serve(
  today: Habits | 'signed-out' | 'error' = HABITS,
  put: 'ok' | 'fail' | 'signed-out' = 'ok',
) {
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === 'PUT') {
      if (put === 'fail') return new Response(null, { status: 500 })
      if (put === 'signed-out') return new Response(null, { status: 401 })
      const key = path.split('/').pop()
      const { done } = JSON.parse(String(init.body)) as { done: boolean }
      return Response.json({
        ...HABITS,
        habits: HABITS.habits.map((h) =>
          h.key === key ? { ...h, done, week_done: h.week_done + (done ? 1 : -1) } : h,
        ),
      })
    }
    if (today === 'signed-out') return new Response(null, { status: 401 })
    if (today === 'error') return new Response(null, { status: 500 })
    return Response.json(today)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

test('shows each habit, ticked or not, with this week so far', async () => {
  serve()
  render(<HabitsCard />)
  const light = await screen.findByRole('button', { name: /Morning light/ })
  expect(light).toHaveAttribute('aria-pressed', 'false')
  expect(light).toHaveTextContent('1 of 3')
  expect(screen.getByRole('button', { name: /Protein target \(165 g\)/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(screen.getByText('Tap each one you did. Days this week: 3 so far.')).toBeInTheDocument()
  expect(screen.getByText('No screens.')).toBeInTheDocument() // under "What counts"
})

test('a tap ticks a habit and another unticks it', async () => {
  const fetchMock = serve()
  render(<HabitsCard />)
  fireEvent.click(await screen.findByRole('button', { name: /Morning light/ }))
  const light = await screen.findByRole('button', { name: /Morning light.*2 of 3/ })
  expect(light).toHaveAttribute('aria-pressed', 'true')
  expect(fetchMock).toHaveBeenLastCalledWith(
    '/api/habits/morning_light',
    expect.objectContaining({ method: 'PUT', body: JSON.stringify({ done: true }) }),
  )
  fireEvent.click(screen.getByRole('button', { name: /Protein/ }))
  expect(await screen.findByRole('button', { name: /Protein.*2 of 3/ })).toHaveAttribute(
    'aria-pressed',
    'false',
  )
})

test('a failed tap says so and keeps the state', async () => {
  serve(HABITS, 'fail')
  render(<HabitsCard />)
  fireEvent.click(await screen.findByRole('button', { name: /Wind-down/ }))
  expect(await screen.findByText(/Check your connection/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Wind-down/ })).toHaveAttribute('aria-pressed', 'false')
})

test('an ended sign-in points to sign in', async () => {
  serve(HABITS, 'signed-out')
  render(<HabitsCard />)
  fireEvent.click(await screen.findByRole('button', { name: /Wind-down/ }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
})

test.each(['signed-out', 'error'] as const)('shows nothing when %s', async (today) => {
  const fetchMock = serve(today)
  const { container } = render(<HabitsCard />)
  await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled())
  await Promise.resolve()
  expect(container).toBeEmptyDOMElement()
})
