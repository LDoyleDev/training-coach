import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import HeartRateZones from './HeartRateZones'

const ZONES = [
  { zone: 1, low: 125, high: 138 },
  { zone: 2, low: 138, high: 151 },
  { zone: 3, low: 151, high: 164 },
  { zone: 4, low: 164, high: 177 },
  { zone: 5, low: 177, high: 190 },
]
const DEFAULT = {
  birth_year: null,
  own_max: null,
  estimated_max: null,
  peak: null,
  rest: 60,
  max: 190,
  zones: ZONES,
}

type Reply = { status: number; body?: unknown }

function serve(routes: Record<string, Reply[]>) {
  const asked: { route: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push({ route, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      const replies = routes[route] ?? [{ status: 500 }]
      const reply = replies.length > 1 ? replies.shift()! : replies[0]
      const body = reply.body === undefined ? null : JSON.stringify(reply.body)
      return new Response(body, { status: reply.status })
    }),
  )
  return asked
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('shows the zones and where max comes from', async () => {
  serve({ 'GET /api/account/heart-rate': [{ status: 200, body: DEFAULT }] })
  render(<HeartRateZones />)
  expect(await screen.findByText(/Resting 60 bpm, max 190 bpm/)).toBeInTheDocument()
  expect(screen.getByText(/until you add your birth year/)).toBeInTheDocument()
  expect(screen.getByText('138–151 bpm')).toBeInTheDocument()
  expect(screen.getByText('2. Easy (zone 2)')).toBeInTheDocument()
})

test.each([
  [{ own_max: 182, max: 182 }, 'your own number'],
  [{ peak: 186, max: 186, estimated_max: 180 }, 'the highest a workout reached'],
  [{ estimated_max: 180, max: 180, peak: 150 }, '208 − 0.7 × your age'],
])('names the source of max', async (change, text) => {
  serve({ 'GET /api/account/heart-rate': [{ status: 200, body: { ...DEFAULT, ...change } }] })
  render(<HeartRateZones />)
  expect(await screen.findByText(new RegExp(text))).toBeInTheDocument()
})

test('saves a birth year and an own max', async () => {
  const asked = serve({
    'GET /api/account/heart-rate': [{ status: 200, body: DEFAULT }],
    'PUT /api/account/heart-rate': [
      { status: 200, body: { ...DEFAULT, birth_year: 1986, own_max: 182, max: 182 } },
    ],
  })
  render(<HeartRateZones />)
  fireEvent.change(await screen.findByLabelText(/Birth year/), { target: { value: '19x86' } })
  fireEvent.change(screen.getByLabelText(/own max heart rate/), { target: { value: '182' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(asked[1].body).toEqual({ birth_year: 1986, own_max: 182 })
  expect(screen.getByText(/max 182 bpm \(from your own number\)/)).toBeInTheDocument()
})

test.each([
  [{ status: 422, body: { detail: 'max heart rate must be from 120 to 230' } }, /from 120 to 230/],
  [{ status: 422, body: { detail: [{ msg: 'bad' }] } }, /Check the numbers/],
  [{ status: 401 }, /Your sign-in ended/],
  [{ status: 500 }, /That didn't work/],
])('a refused save says why', async (reply, text) => {
  serve({
    'GET /api/account/heart-rate': [{ status: 200, body: DEFAULT }],
    'PUT /api/account/heart-rate': [reply],
  })
  render(<HeartRateZones />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
  expect(await screen.findByText(text)).toBeInTheDocument()
})

test('hidden when signed out or the server fails', async () => {
  serve({ 'GET /api/account/heart-rate': [{ status: 401 }] })
  const { container } = render(<HeartRateZones />)
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(container).toBeEmptyDOMElement()
})
