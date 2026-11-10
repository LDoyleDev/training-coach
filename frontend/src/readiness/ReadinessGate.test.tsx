import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Readiness } from '../api'
import ReadinessGate from './ReadinessGate'
import { NOTES, QUESTIONS, VERSION } from './questions'

const DUE: Readiness = { version: VERSION, due: true, answered_at: null, ask_again_after: null }
const ANSWERED: Readiness = {
  version: VERSION,
  due: false,
  answered_at: '2026-10-01T08:00:00Z',
  ask_again_after: '2027-10-01T08:00:00Z',
}

function serve(readiness: Readiness | null | 'error', saved = 200) {
  const sent: unknown[] = []
  const fetch = vi.fn(async (_path: string, init?: RequestInit) => {
    if (init?.method === 'PUT') {
      sent.push(JSON.parse(String(init.body)))
      return saved === 200 ? Response.json(ANSWERED) : new Response(null, { status: saved })
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

/** Answer every question: "Yes" to the first (active), then the given answer to the rest. */
async function answerAll(rest: 'Yes' | 'No' | 'Not sure', except: Record<number, string> = {}) {
  for (let i = 0; i < QUESTIONS.length; i++) {
    const name = except[i] ?? (i === 0 ? 'Yes' : rest)
    fireEvent.click(await screen.findByRole('button', { name }))
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  open('/')
})

test('when the questions are due they come first, then the note, then the page', async () => {
  const { sent } = serve(DUE)
  show()
  expect(await screen.findByText(QUESTIONS[0].text)).toBeInTheDocument()
  expect(screen.queryByText('the page')).not.toBeInTheDocument()
  expect(screen.getByText('Question 1 of 10')).toBeInTheDocument()
  expect(screen.getByText(/Your answers stay on this device/)).toBeInTheDocument()
  await answerAll('No')
  expect(await screen.findByRole('heading', { name: NOTES.easy.title })).toBeInTheDocument()
  expect(screen.getByText(/We'll ask again in a year/)).toBeInTheDocument()
  expect(screen.getByText('All stop signs')).toBeInTheDocument()
  expect(sent).toEqual([{ version: VERSION }]) // never an answer
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('a symptom suggests a doctor before starting, and still lets them go on', async () => {
  serve(DUE)
  show()
  await answerAll('No', { 5: 'Yes' }) // chest pain
  expect(await screen.findByRole('heading', { name: NOTES.doctor_first.title })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('"Not sure" counts as yes', async () => {
  serve(DUE)
  show()
  await answerAll('No', { 3: 'Not sure' }) // diabetes or kidney disease
  expect(
    await screen.findByRole('heading', { name: NOTES.easy_ask_before_hard.title }),
  ).toBeInTheDocument()
})

test('the fainting question explains what not to count', async () => {
  serve(DUE)
  show()
  for (let i = 0; i < 7; i++) fireEvent.click(await screen.findByRole('button', { name: 'No' }))
  expect(screen.getByText(QUESTIONS[7].text)).toBeInTheDocument()
  expect(screen.getByText(/from breathing too fast/)).toBeInTheDocument()
})

test('Back goes to the previous question', async () => {
  serve(DUE)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Yes' }))
  expect(screen.getByText(QUESTIONS[1].text)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  expect(screen.getByText(QUESTIONS[0].text)).toBeInTheDocument()
})

test('answered and still current: straight to the page', async () => {
  const { fetch } = serve(ANSWERED)
  show()
  expect(await screen.findByText('the page')).toBeInTheDocument()
  expect(screen.queryByText(QUESTIONS[0].text)).not.toBeInTheDocument()
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

test.each(['/signin', '/readiness', '/start'])('%s opens without the check', (path) => {
  open(path)
  const { fetch } = serve(DUE)
  show()
  expect(screen.getByText('the page')).toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})

test('a failed save still shows the note, and says it will ask again', async () => {
  serve(DUE, 500)
  show()
  await answerAll('No')
  expect(await screen.findByRole('alert')).toHaveTextContent("we'll ask again next time")
  expect(screen.getByRole('heading', { name: NOTES.easy.title })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('newer questions on the server: asks to reload', async () => {
  serve(DUE, 409)
  show()
  await answerAll('No')
  expect(await screen.findByRole('alert')).toHaveTextContent('Reload to answer the new ones')
})

test('signed out while saving: the note, then through to the page', async () => {
  serve(DUE, 401)
  show()
  await answerAll('No')
  expect(await screen.findByRole('heading', { name: NOTES.easy.title })).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
