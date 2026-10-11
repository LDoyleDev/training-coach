import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Readiness } from '../api'
import ReadinessGate from './ReadinessGate'

const QUESTIONS = [
  { key: 'heart', text: 'Heart condition?' },
  { key: 'joints', text: 'Joint problem?' },
]
const DUE: Readiness = {
  questions: QUESTIONS,
  status: 'due',
  answers: null,
  answered_at: null,
  ask_again_after: null,
}
const CLEAR: Readiness = {
  ...DUE,
  status: 'clear',
  answers: { heart: false, joints: false },
  answered_at: '2026-10-01T08:00:00Z',
  ask_again_after: '2027-04-01T08:00:00Z',
}

function serve(readiness: Readiness | null | 'error', saved: string | number = 'clear') {
  const sent: unknown[] = []
  const fetch = vi.fn(async (_path: string, init?: RequestInit) => {
    if (init?.method === 'PUT') {
      sent.push(JSON.parse(String(init.body)))
      if (typeof saved === 'number') return new Response(null, { status: saved })
      return Response.json({ status: saved })
    }
    if (readiness === 'error') return new Response(null, { status: 500 })
    if (readiness === null) return new Response(null, { status: 401 })
    return Response.json(readiness)
  })
  vi.stubGlobal('fetch', fetch)
  return { sent, fetch }
}

const open = (path: string) => window.history.replaceState(null, '', path)
const show = () =>
  render(
    <ReadinessGate>
      <p>the page</p>
    </ReadinessGate>,
  )

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  open('/')
})

test('when the questions are due they come first, then what they mean, then the page', async () => {
  const { sent } = serve(DUE, 'clear')
  show()
  expect(await screen.findByText('Heart condition?')).toBeInTheDocument()
  expect(screen.queryByText('the page')).not.toBeInTheDocument()
  expect(screen.getByText('Question 1 of 2')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  expect(screen.getByText('Joint problem?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  expect(await screen.findByRole('heading', { name: 'Go as planned' })).toBeInTheDocument()
  expect(sent).toEqual([{ answers: { heart: false, joints: false } }])
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('a yes says to go easier on hard days', async () => {
  serve(DUE, 'see_doctor')
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Yes' }))
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  expect(await screen.findByRole('heading', { name: 'Go easier on hard days' })).toBeInTheDocument()
  expect(screen.getByText(/Check with a doctor before hard efforts/)).toBeInTheDocument()
})

test('Back goes to the previous question and keeps the answers', async () => {
  const { sent } = serve(DUE)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Yes' }))
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  expect(screen.getByText('Heart condition?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  fireEvent.click(screen.getByRole('button', { name: 'Yes' }))
  await screen.findByRole('button', { name: 'Continue' })
  expect(sent).toEqual([{ answers: { heart: false, joints: true } }])
})

test('answered and still current: straight to the page', async () => {
  const { fetch } = serve(CLEAR)
  show()
  expect(await screen.findByText('the page')).toBeInTheDocument()
  expect(screen.queryByText('Heart condition?')).not.toBeInTheDocument()
  expect(fetch).toHaveBeenCalledTimes(1)
})

test('Not now lets you through without saving anything', async () => {
  const { sent } = serve(DUE)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Not now' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
  expect(sent).toEqual([])
})

test.each([
  ['a server error', 'error' as const],
  ['signed out', null],
])('%s never blocks the page', async (_name, readiness) => {
  serve(readiness)
  show()
  expect(await screen.findByText('the page')).toBeInTheDocument()
})

test('a server that never answers lets you through after a few seconds', async () => {
  vi.useFakeTimers()
  vi.stubGlobal(
    'fetch',
    vi.fn(
      (_path: string, init?: RequestInit) =>
        new Promise((_resolve, reject) =>
          init?.signal?.addEventListener('abort', () => reject(new DOMException('', 'AbortError'))),
        ),
    ),
  )
  show()
  expect(screen.getByText('Loading…')).toBeInTheDocument()
  await act(() => vi.advanceTimersByTimeAsync(4000))
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('the page that was opened is the one shown after answering', async () => {
  open('/session?day=3')
  serve(DUE)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Not now' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
  expect(window.location.pathname + window.location.search).toBe('/session?day=3')
})

test.each(['/signin', '/readiness'])('%s opens without the check', (path) => {
  open(path)
  const { fetch } = serve(DUE)
  show()
  expect(screen.getByText('the page')).toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})

test('a failed save says so; Try again saves the same answers; Not now still lets you through', async () => {
  const { sent } = serve(DUE, 500)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'No' }))
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't save your answers")
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  expect(sent).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'Not now' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('signed out while saving: through to the page, which asks to sign in', async () => {
  serve(DUE, 401)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'No' }))
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  expect(await screen.findByText('the page')).toBeInTheDocument()
})
