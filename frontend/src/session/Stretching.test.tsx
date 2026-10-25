import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Routine } from '../api'
import Stretching from './Stretching'

vi.mock('../hiit/sounds', () => ({ unlockAudio: vi.fn(), playChange: vi.fn() }))

// Couch 0-160 (both sides, two rounds), fold 160-275: 4 min 35 s, the gaps included.
const ROUTINE: Routine = {
  session: 'Legs',
  minutes: 10,
  hold_seconds: 30,
  position_seconds: 15,
  release_seconds: 5,
  steps: [
    { slug: 'couch', name: 'Couch stretch', rounds: 2, per_side: true, cue: 'Knee to the wall.' },
    { slug: 'fold', name: 'Forward fold', rounds: 3, per_side: false, cue: 'Soft knees.' },
  ],
}

/** A fake API: the routine answer and the logged answer, or a failure. */
function serve(routine: Routine | null | 'fail' | 'signed-out' = ROUTINE, logged = true) {
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === 'POST') return Response.json({ logged })
    if (path === '/api/settings') return Response.json({ sound: 'chime' })
    if (routine === 'fail') return new Response(null, { status: 500 })
    if (routine === 'signed-out') return new Response(null, { status: 401 })
    if (routine === null) return new Response(null, { status: 404 })
    expect(path).toBe('/api/session/stretching/7?minutes=10')
    return Response.json(routine)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const posted = (fetchMock: ReturnType<typeof serve>, minutes: number) =>
  expect(fetchMock).toHaveBeenLastCalledWith(
    '/api/session/stretching/7',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ minutes }) }),
  )

test('choosing a time shows the overview, and Done logs it without the player', async () => {
  const fetchMock = serve()
  render(<Stretching workoutId={7} />)
  fireEvent.click(screen.getByRole('button', { name: '10 min' }))
  expect(await screen.findByText('Couch stretch')).toBeInTheDocument()
  expect(screen.getByText(/4 min 35 s in all/)).toBeInTheDocument()
  expect(screen.getByText('· 2 × 30 s each side')).toBeInTheDocument()
  expect(screen.getByText('Soft knees.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Done stretching' }))
  expect(await screen.findByText('Logged 10 min of stretching.')).toBeInTheDocument()
  posted(fetchMock, 10)
})

async function guided() {
  const fetchMock = serve()
  render(<Stretching workoutId={7} />)
  fireEvent.click(screen.getByRole('button', { name: '10 min' }))
  await screen.findByRole('button', { name: 'Start stretching' })
  vi.useFakeTimers()
  fireEvent.click(screen.getByRole('button', { name: 'Start stretching' }))
  return fetchMock
}

test('followed to the end, it logs the real minutes done by itself', async () => {
  const fetchMock = await guided()
  await act(async () => vi.advanceTimersByTime(275_400))
  vi.useRealTimers()
  expect(await screen.findByText('Logged 5 min of stretching.')).toBeInTheDocument()
  posted(fetchMock, 5)
})

test('stopped early, nothing is logged unless asked', async () => {
  const fetchMock = await guided()
  await act(async () => vi.advanceTimersByTime(30_000))
  fireEvent.click(screen.getByRole('button', { name: 'Stop early' }))
  fireEvent.click(screen.getByRole('button', { name: "Don't log it" }))
  expect(screen.getByText('Not logged.')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})

test('a second Done says it was already logged', async () => {
  serve(ROUTINE, false)
  render(<Stretching workoutId={7} />)
  fireEvent.click(screen.getByRole('button', { name: '10 min' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Done stretching' }))
  expect(await screen.findByText(/already logged/)).toBeInTheDocument()
})

test('no routine for the workout says so', async () => {
  serve(null)
  render(<Stretching workoutId={7} />)
  fireEvent.click(screen.getByRole('button', { name: '10 min' }))
  expect(await screen.findByText('No stretching for this workout.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '10 min' })).toBeInTheDocument()
})

test('a failed request keeps the choices', async () => {
  serve('fail')
  render(<Stretching workoutId={7} />)
  fireEvent.click(screen.getByRole('button', { name: '10 min' }))
  expect(await screen.findByText(/Check your connection/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '20 min' })).toBeEnabled()
})

test('an ended sign-in points to sign in', async () => {
  serve('signed-out')
  render(<Stretching workoutId={7} />)
  fireEvent.click(screen.getByRole('button', { name: '10 min' }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
})
