import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { DailyCheck } from '../api'
import DailyCheckGate from './DailyCheckGate'

const OPEN: DailyCheck = {
  day: '2026-10-11',
  questions: [
    {
      key: 'sleep',
      text: 'How did you sleep?',
      options: [
        { value: 'good', label: 'Good' },
        { value: 'ok', label: 'OK' },
        { value: 'poor', label: 'Poorly' },
      ],
    },
    {
      key: 'soreness',
      text: 'How sore are you?',
      options: [
        { value: 'none', label: 'Not sore' },
        { value: 'some', label: 'A bit sore' },
        { value: 'a_lot', label: 'Very sore' },
      ],
    },
    {
      key: 'energy',
      text: "How's your energy?",
      options: [
        { value: 'high', label: 'High' },
        { value: 'normal', label: 'Normal' },
        { value: 'low', label: 'Low' },
      ],
    },
  ],
  answers: null,
  advice: null,
}
const advised = (kind: 'as_planned' | 'lighter' | 'rest', title: string): DailyCheck => ({
  ...OPEN,
  answers: { sleep: 'poor', soreness: 'a_lot', energy: 'low' },
  advice: { kind, title, text: `${title}, because.`, summary: 'a line' },
})
const REST = advised('rest', 'Take a rest day')
const SESSION = { template_id: 7, name: 'Legs' }

type Rest = 'ok' | 'advanced' | 'stale' | 'none' | 500 | 401

function serve(
  check: DailyCheck | null | 'error',
  saved: DailyCheck | number = REST,
  rest: Rest = 'ok',
) {
  const sent: unknown[] = []
  const rested: unknown[] = []
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    if (path === '/api/session/today')
      return Response.json({ session: rest === 'none' ? null : SESSION, progress: null })
    if (path === '/api/today/rest') {
      rested.push(JSON.parse(String(init?.body)))
      if (typeof rest === 'number') return new Response(null, { status: rest })
      if (rest === 'stale') return new Response(null, { status: 409 })
      return Response.json({
        session: 'Legs',
        advanced: rest === 'advanced',
        today: {},
        undo: null,
      })
    }
    if (init?.method === 'PUT') {
      sent.push(JSON.parse(String(init.body)))
      if (typeof saved === 'number') return new Response(null, { status: saved })
      return Response.json(saved)
    }
    if (check === 'error') return new Response(null, { status: 500 })
    if (check === null) return new Response(null, { status: 401 })
    return Response.json(check)
  })
  vi.stubGlobal('fetch', fetch)
  return { sent, rested, fetch }
}

const open = (path: string) => window.history.replaceState(null, '', path)
const show = () =>
  render(
    <DailyCheckGate>
      <p>the page</p>
    </DailyCheckGate>,
  )
const tap = (name: string) => fireEvent.click(screen.getByRole('button', { name }))
async function answerAll() {
  fireEvent.click(await screen.findByRole('button', { name: 'Poorly' }))
  tap('Very sore')
  tap('Low')
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  open('/')
})

test('unanswered today: three questions, one tap each, then the advice, then the page', async () => {
  const { sent } = serve(OPEN, advised('as_planned', 'Go as planned'))
  show()
  expect(await screen.findByText('How did you sleep?')).toBeInTheDocument()
  expect(screen.queryByText('the page')).not.toBeInTheDocument()
  expect(screen.getByText('Question 1 of 3')).toBeInTheDocument()
  tap('Good')
  expect(screen.getByText('How sore are you?')).toBeInTheDocument()
  tap('Back')
  tap('OK')
  tap('Not sore')
  tap('High')
  expect(await screen.findByRole('heading', { name: 'Go as planned' })).toBeInTheDocument()
  expect(sent).toEqual([{ sleep: 'ok', soreness: 'none', energy: 'high' }])
  expect(screen.queryByRole('button', { name: 'Rest today' })).not.toBeInTheDocument()
  tap('Continue')
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('go lighter offers only Continue', async () => {
  serve(OPEN, advised('lighter', 'Go lighter today'))
  show()
  await answerAll()
  expect(await screen.findByRole('heading', { name: 'Go lighter today' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Rest today' })).not.toBeInTheDocument()
})

test.each([
  ['ok' as const, 'Rest today. Legs moves to tomorrow.'],
  ['advanced' as const, 'Legs logged as a rest day. Enjoy it.'],
  ['stale' as const, "Today's session changed meanwhile, so nothing was rested."],
  ['none' as const, 'Nothing is left to train today'],
  [500 as const, "Couldn't rest today."],
])('a rest day offers Rest today in one tap (%s)', async (rest, said) => {
  const { rested } = serve(OPEN, REST, rest)
  show()
  await answerAll()
  expect(await screen.findByRole('heading', { name: 'Take a rest day' })).toBeInTheDocument()
  tap('Rest today')
  expect(await screen.findByText(said, { exact: false })).toBeInTheDocument()
  expect(rested).toEqual(rest === 'none' ? [] : [{ template_id: 7 }])
  tap('Continue')
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('signed out while resting: through to the page', async () => {
  serve(OPEN, REST, 401)
  show()
  await answerAll()
  fireEvent.click(await screen.findByRole('button', { name: 'Rest today' }))
  expect(await screen.findByText('the page')).toBeInTheDocument()
})

test('answered today: straight to the page', async () => {
  const { fetch } = serve(REST)
  show()
  expect(await screen.findByText('the page')).toBeInTheDocument()
  expect(fetch).toHaveBeenCalledTimes(1)
})

test('Not now lets you through without saving anything', async () => {
  const { sent } = serve(OPEN)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Not now' }))
  expect(screen.getByText('the page')).toBeInTheDocument()
  expect(sent).toEqual([])
})

test.each([
  ['a server error', 'error' as const],
  ['signed out', null],
])('%s never blocks the page', async (_name, check) => {
  serve(check)
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

test.each(['/signin', '/readiness'])('%s opens without the check', (path) => {
  open(path)
  const { fetch } = serve(OPEN)
  show()
  expect(screen.getByText('the page')).toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})

test('a failed save says so; Try again saves the same answers', async () => {
  const { sent } = serve(OPEN, 500)
  show()
  await answerAll()
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't save your answers")
  tap('Try again')
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  expect(sent).toHaveLength(2)
  tap('Not now')
  expect(screen.getByText('the page')).toBeInTheDocument()
})

test('signed out while saving: through to the page', async () => {
  serve(OPEN, 401)
  show()
  await answerAll()
  expect(await screen.findByText('the page')).toBeInTheDocument()
})

test('last night on the band pre-selects the sleep answer, still one tap to confirm', async () => {
  const { sent } = serve(
    { ...OPEN, suggested_sleep: 'good', band_asleep_min: 440 },
    advised('as_planned', 'Go as planned'),
  )
  show()
  expect(
    await screen.findByText('Your band: 7 h 20 min asleep. Tap to confirm.'),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Good' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'OK' })).toHaveAttribute('aria-pressed', 'false')
  expect(sent).toEqual([]) // nothing is answered until tapped
  tap('Good')
  expect(screen.queryByText(/Your band/)).not.toBeInTheDocument() // only on the sleep question
  tap('Not sore')
  tap('High')
  await screen.findByRole('heading', { name: 'Go as planned' })
  expect(sent).toEqual([{ sleep: 'good', soreness: 'none', energy: 'high' }])
})
