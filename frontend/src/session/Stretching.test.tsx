import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Routine } from '../api'
import Stretching from './Stretching'

const ROUTINE: Routine = {
  session: 'Legs',
  minutes: 10,
  hold_seconds: 30,
  steps: [
    { name: 'Couch stretch', rounds: 2, per_side: true, cue: 'Knee to the wall.' },
    { name: 'Forward fold', rounds: 3, per_side: false, cue: 'Soft knees.' },
  ],
}

/** A fake API: the routine answer and the logged answer, or a failure. */
function serve(routine: Routine | null | 'fail' = ROUTINE, logged = true) {
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === 'POST') return Response.json({ logged })
    if (routine === 'fail') return new Response(null, { status: 500 })
    if (routine === null) return new Response(null, { status: 404 })
    expect(path).toBe('/api/session/stretching/7?minutes=10')
    return Response.json(routine)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

test('choosing a time shows the routine, and Done logs it', async () => {
  const fetchMock = serve()
  render(<Stretching workoutId={7} />)
  fireEvent.click(screen.getByRole('button', { name: '10 min' }))
  expect(await screen.findByText('Couch stretch')).toBeInTheDocument()
  expect(screen.getByText(/2 rounds of 30 s each side/)).toBeInTheDocument()
  expect(screen.getByText('Soft knees.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Done stretching' }))
  expect(await screen.findByText('Logged 10 min of stretching.')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenLastCalledWith(
    '/api/session/stretching/7',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ minutes: 10 }) }),
  )
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
